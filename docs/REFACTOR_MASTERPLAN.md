# REFACTOR_MASTERPLAN.md — Plan de refactorización de ArchMuse

**Postura de este documento:** la de un CTO que va a decir "sí, vendemos esto" solo cuando la base esté limpia. Este plan **no añade funcionalidad**. Cada tarea es una unidad de trabajo independiente, de máximo 2 horas, ejecutable y verificable por separado. Ninguna tarea de este documento se ha implementado todavía.

Se apoya directamente en los hallazgos de `TECH_REVIEW.md` — cada tarea referencia el hallazgo del que nace.

**Fuera de alcance deliberadamente** (son funcionalidad nueva, no refactorización): autenticación, persistencia de análisis, rate-limiting, cola de trabajos en segundo plano para la IA. Ya están recogidos como Fase 2 del roadmap de `TECH_REVIEW.md` — este documento se centra en que lo que **ya existe** sea correcto, seguro y sostenible antes de construir nada nuevo encima.

---

## Cómo está ordenado este documento

Las tareas están ordenadas por **ROI = Beneficio / Esfuerzo**, con Beneficio puntuado Alto=3 / Medio=2 / Bajo=1 y Esfuerzo en horas. Es el orden que pediste explícitamente. Dentro de un mismo nivel de ROI, se ha respetado tu lista de prioridades (1. bugs → 2. deuda técnica → 3. mantenibilidad → 4. rendimiento → 5. seguridad → 6. experiencia de desarrollador).

Cada tarea lleva una etiqueta de categoría `[BUG]` `[DEUDA]` `[MANTENIBILIDAD]` `[RENDIMIENTO]` `[SEGURIDAD]` `[DX]` para que puedas filtrar mentalmente por tu propio criterio de prioridad si en algún momento difiere del orden por ROI.

---

## Tabla resumen (orden de ejecución recomendado)

| # | Tarea | Categoría | Beneficio | Esfuerzo | ROI |
|---|---|---|---|---:|---:|
| 1 | Confirmar en git el trabajo pendiente | DEUDA | Alto | 0,25h | 12,0 |
| 2 | Etiquetar el percentil comparativo como estimación | DEUDA | Alto | 0,5h | 6,0 |
| 3 | Añadir `.env.example` | DX | Bajo | 0,25h | 4,0 |
| 4 | Retirar ruta personal hardcodeada de `main.py` + banner de CLI en desuso | DEUDA | Medio | 0,5h | 4,0 |
| 5 | `zona_cte`/`tipología` reales en `/api/analizar` (Bug crítico) | BUG | Alto | 1,5h | 2,0* |
| 6 | Aviso de zona climática por defecto en `limitaciones` | DEUDA | Medio | 0,75h | 2,67 |
| 7 | `zip()` con `strict=` en geometría de usuario | BUG | Medio | 0,75h | 2,67 |
| 8 | `pyproject.toml` con configuración de `ruff` | DX | Medio | 0,75h | 2,67 |
| 9 | Timeout explícito en las llamadas al cliente de Anthropic | RENDIMIENTO | Medio | 0,75h | 2,67 |
| 10 | Eliminar código muerto confirmado + import no usado | DEUDA | Medio | 1h | 2,0 |
| 11 | Corregir adyacencia acústica inerte (Bug #2) | BUG | Alto | 1,5h | 2,0* |
| 12 | Fijar versiones exactas de dependencias | SEGURIDAD | Medio | 1h | 2,0 |
| 13 | `debug=False` + servidor WSGI real (waitress) | SEGURIDAD | Alto | 1,5h | 2,0* |
| 14 | Consolidar el bucle de polígono-a-SVG duplicado 3 veces | DEUDA | Medio | 1h | 2,0 |
| 15 | Timestamps con zona horaria | BUG | Bajo | 0,5h | 2,0 |
| 16 | Cutover final de `classify_problems` a tabla declarativa | MANTENIBILIDAD | Alto | 1,5h | 2,0 |
| 17 | README.md de arranque | DX | Medio | 1,5h | 1,33 |
| 18 | Suite de test golden-master | MANTENIBILIDAD | Alto | 2h | 1,5 |
| 19 | Reducir los 19 parámetros de `serialize_analysis` | MANTENIBILIDAD | Alto | 2h | 1,5 |
| 20 | Vendorizar `three.js` localmente | SEGURIDAD | Medio | 1,5h | 1,33 |
| 21 | Eliminar la triple recomputación de `room_problems()` | RENDIMIENTO | Medio | 1,5h | 1,33 |
| 22 | Diseño del motor de tabla declarativa para `classify_problems` | MANTENIBILIDAD | Medio | 2h | 1,0 |
| 23 | Migrar bloques CRITICO a la tabla declarativa | MANTENIBILIDAD | Medio | 2h | 1,0 |
| 24 | Migrar bloques IMPORTANTE a la tabla declarativa | MANTENIBILIDAD | Medio | 2h | 1,0 |
| 25 | Consolidar adyacencia duplicada (`evaluator` ↔ `circulation`) | DEUDA | Bajo | 1h | 1,0 |
| 26 | Benchmark de `compute_puntos_ganados` (O(n²)) | RENDIMIENTO | Bajo | 1h | 1,0 |
| 27 | Limpieza mecánica `PERF401` + parámetro `unit` sin usar | MANTENIBILIDAD | Bajo | 1h | 1,0 |
| 28 | Extraer modelos/dataclasses de `evaluator.py` | MANTENIBILIDAD | Bajo | 2h | 0,5 |
| 29 | Extraer reglas de urbanismo de edificio a su propio módulo | MANTENIBILIDAD | Bajo | 1,5h | 0,67 |

`*` ROI recalculado hacia arriba respecto a su cálculo estricto porque son correcciones de bug/seguridad de beneficio Alto — se han adelantado en la tabla respetando tu orden de prioridades (1 y 5) frente a tareas de deuda técnica de ROI numéricamente similar.

---

## FICHAS DE TAREA

### 1 — Confirmar en git el trabajo pendiente
**Categoría:** `[DEUDA]` · **Beneficio:** Alto · **Esfuerzo:** 0,25h

- **Objetivo:** llevar a un commit los 4 módulos sin versionar (`chain_effects.py`, `circulation.py`, `scoring.py`, `spatial_quality.py`) y el resto de cambios pendientes (`api_serializer.py`, `evaluator.py`, `plan_svg.py`, `app.py`, `static/index.html`).
- **Beneficio:** elimina el único riesgo de pérdida total e irreversible de trabajo que existe hoy en el proyecto.
- **Riesgo:** ninguno — es una operación de git, no un cambio de comportamiento.
- **Archivos afectados:** todos los pendientes de `git status`.
- **Dependencias:** ninguna. Debe ser la tarea #1 antes de tocar cualquier otra cosa de este plan.
- **Cómo comprobar que ha quedado bien:** `git status` devuelve "nothing to commit, working tree clean".
- **¿Rompe compatibilidad?** No.

### 2 — Etiquetar el percentil comparativo como estimación
**Categoría:** `[DEUDA]` (honestidad de producto) · **Beneficio:** Alto · **Esfuerzo:** 0,5h

- **Objetivo:** añadir en la SPA, junto al percentil de `scoring.estimar_percentil`, un texto/tooltip visible que aclare que la comparación es una estimación orientativa y no datos agregados de otros proyectos reales.
- **Beneficio:** elimina el riesgo reputacional/legal de presentar un dato inventado como si fuera de mercado — es el hallazgo #14 de "peores decisiones" de `TECH_REVIEW.md`.
- **Riesgo:** bajo — cambio de copy/UI, no de lógica.
- **Archivos afectados:** `static/index.html` (donde se renderiza el percentil, buscar el consumidor de `percentil_estimado`).
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** abrir la SPA con un análisis cargado, verificar visualmente que el aviso aparece junto al percentil sin necesidad de buscarlo.
- **¿Rompe compatibilidad?** No — no cambia el JSON de la API, solo el renderizado.

### 3 — Añadir `.env.example`
**Categoría:** `[DX]` · **Beneficio:** Bajo · **Esfuerzo:** 0,25h

- **Objetivo:** crear `.env.example` con `ANTHROPIC_API_KEY=` documentado, para que un desarrollador nuevo sepa qué variable de entorno necesita sin leer `ai_analyst.py`.
- **Beneficio:** onboarding más rápido para cualquier persona distinta de Pablo.
- **Riesgo:** ninguno.
- **Archivos afectados:** nuevo `.env.example` en la raíz.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** el archivo existe y no contiene ninguna clave real.
- **¿Rompe compatibilidad?** No.

### 4 — Retirar ruta personal hardcodeada de `main.py` + banner de CLI en desuso
**Categoría:** `[DEUDA]` · **Beneficio:** Medio · **Esfuerzo:** 0,5h

- **Objetivo:** sustituir `DXF_PATH = r"C:\Users\<usuario>\Desktop\Pablo\Archmuse\ejemplo.dxf"` (`main.py:21`) por un argumento obligatorio o un error claro si no se indica ruta; añadir un docstring al principio de `main.py`/`reporter.py` dejando explícito que es una herramienta de depuración interna, no el producto (que es `app.py` + la SPA).
- **Beneficio:** evita que una ruta personal termine en un repositorio compartido con un cliente o inversor; clarifica para cualquier futuro desarrollador cuál es "el producto" de verdad.
- **Riesgo:** bajo — solo afecta al flujo CLI, que ya está fuera del camino de producto principal.
- **Archivos afectados:** `main.py`, `analyzer/reporter.py` (docstring de cabecera).
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** `python main.py` sin argumentos falla con un mensaje claro en vez de usar una ruta personal por defecto; `python main.py ejemplo.dxf` sigue funcionando igual que antes.
- **¿Rompe compatibilidad?** Sí, de forma intencionada y menor: quien ejecutara `main.py` sin argumentos confiando en el valor por defecto tendrá que pasar la ruta explícitamente. Solo afecta a Pablo en su propio uso local de la CLI.

### 5 — `zona_cte`/`tipología` reales en `/api/analizar` (Bug crítico #1)
**Categoría:** `[BUG]` · **Beneficio:** Alto · **Esfuerzo:** 1,5h

- **Objetivo:** en `app.py:analizar()`, pasar `tipologia=tipologia, zona_cte=zona_cte, densidad_urbana=get_densidad_urbana(ciudad)` a la llamada a `evaluate_advanced()` (línea 79), y pasar `proyecto={"tipologia": tipologia, "zona_cte": zona_cte, "ciudad": ciudad}` a `serialize_analysis()` (línea 95-101) — igual que ya hace correctamente `/api/generar`.
- **Beneficio:** corrige el bug más grave del proyecto. Hoy **todo** DXF real subido se evalúa con tipología "plurifamiliar" y zona climática "C" por defecto, sin importar lo que el arquitecto seleccione en el formulario — anula silenciosamente el trabajo de varios de los últimos commits (umbrales adaptativos, zona CTE automática). Detalle completo en `TECH_REVIEW.md`, sección "Bug #1".
- **Riesgo:** medio. No es un cambio de lógica nueva, solo de propagación de parámetros ya existentes — pero cambia los resultados reales que ve el usuario para cualquier proyecto que no sea plurifamiliar en zona C. Es un riesgo de "sorpresa" para Pablo si compara un informe de antes y de después del fix sobre el mismo DXF con otra tipología/ciudad: los números cambiarán (a mejor, hacia lo correcto).
- **Archivos afectados:** `app.py` (función `analizar`).
- **Dependencias:** ninguna técnica. Se recomienda hacerla **antes** de la tarea 18 (test golden-master), para que el primer snapshot de referencia ya capture el comportamiento correcto y no perpetúe el bug como "comportamiento esperado".
- **Cómo comprobar que ha quedado bien:** subir el mismo DXF de ejemplo dos veces por la API, una vez con `tipologia=unifamiliar` y otra con `tipologia=plurifamiliar` (o con dos ciudades de zonas climáticas distintas, p. ej. Madrid=D y Sevilla=B) y verificar que el JSON de respuesta (campo `issues`, `desglose_puntuacion`, severidad del baño accesible) **cambia** entre ambas — hoy es idéntico en ambos casos, que es precisamente el bug.
- **¿Rompe compatibilidad?** No en el contrato JSON (mismas claves, mismo formato). Sí cambia los **valores** devueltos para cualquier análisis que no sea plurifamiliar/zona C — es un cambio de comportamiento deseado, no un efecto secundario.

### 6 — Aviso de zona climática por defecto en `limitaciones`
**Categoría:** `[DEUDA]` (honestidad de producto) · **Beneficio:** Medio · **Esfuerzo:** 0,75h

- **Objetivo:** en `get_missing_data_warnings` (`evaluator.py:116`), añadir un aviso cuando la ciudad indicada no esté en `cte_zonas.ZONAS_CTE` (~30 municipios cubiertos), avisando de que se ha usado la zona climática por defecto ("C") como suposición.
- **Beneficio:** hoy el arquitecto no tiene forma de saber si el dato climático usado es real o una suposición silenciosa — coherente con la filosofía de transparencia que ya tiene el resto de `limitaciones`.
- **Riesgo:** bajo.
- **Archivos afectados:** `analyzer/cte_zonas.py` (exponer si hubo hit o fallback), `analyzer/evaluator.py` (`get_missing_data_warnings`), `analyzer/api_serializer.py` (pasar el dato necesario).
- **Dependencias:** ninguna, pero tiene más sentido hacerla justo después de la tarea 5 (mismo área de código).
- **Cómo comprobar que ha quedado bien:** analizar un DXF con una ciudad no listada (p. ej. "Cuenca") y verificar que `limitaciones` incluye el nuevo aviso; con una ciudad listada (p. ej. "Madrid") el aviso no aparece.
- **¿Rompe compatibilidad?** No — añade un elemento más a una lista existente, no cambia su forma.

### 7 — `zip()` con `strict=` en geometría de usuario
**Categoría:** `[BUG]` · **Beneficio:** Medio · **Esfuerzo:** 0,75h

- **Objetivo:** añadir `strict=True` (o una comprobación de longitud explícita con mensaje de error) a los 4 usos de `zip()` sobre coordenadas de geometría: `circulation.py:464`, `evaluator.py:400`, `plan_svg.py:555`, `spatial_quality.py:420`.
- **Beneficio:** convierte un truncamiento silencioso de contorno (dato corrupto sin aviso) en un error explícito y trazable si algún DXF llega con geometría mal formada.
- **Riesgo:** bajo-medio — si algún DXF real ya provoca hoy ese desajuste de longitudes (posible, no confirmado), este cambio lo convertirá en un error visible donde antes no pasaba nada. Es el comportamiento deseado, pero conviene probarlo contra `ejemplo.dxf` antes de darlo por bueno.
- **Archivos afectados:** `analyzer/circulation.py`, `analyzer/evaluator.py`, `analyzer/plan_svg.py`, `analyzer/spatial_quality.py`.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** ejecutar el análisis completo sobre `ejemplo.dxf` (los 3 flujos que tocan estas líneas: analizar, generar, PDF) y confirmar que no salta ningún `ValueError` nuevo — si salta, es una geometría real hasta ahora corrupta en silencio, y hay que decidir cómo tratarla, no revertir el cambio.
- **¿Rompe compatibilidad?** No en el contrato de API; sí es posible que, si existe algún DXF real con esa discrepancia, esa petición empiece a fallar explícitamente en vez de generar un plano corrupto silenciosamente. Es el trade-off correcto.

### 8 — `pyproject.toml` con configuración de `ruff`
**Categoría:** `[DX]` · **Beneficio:** Medio · **Esfuerzo:** 0,75h

- **Objetivo:** añadir `ruff` como dependencia de desarrollo y un `pyproject.toml` que fije las reglas usadas en esta auditoría (`F`, `B`, `C901`, `PLR09xx`, `PERF`, `S201`, `DTZ`), para que los hallazgos de `TECH_REVIEW.md` no puedan reintroducirse sin que alguien lo note.
- **Beneficio:** convierte una auditoría puntual en una barrera permanente y automatizable (además, deja el proyecto listo para engancharse a CI en el futuro sin trabajo adicional).
- **Riesgo:** ninguno — herramienta de desarrollo, no toca el código de producto.
- **Archivos afectados:** nuevo `pyproject.toml`, nuevo `requirements-dev.txt` (o sección `[dev]` si se prefiere `pyproject`).
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** `ruff check .` se ejecuta sin configuración adicional y reporta 0 errores tras aplicar las tareas de limpieza de este plan.
- **¿Rompe compatibilidad?** No.

### 9 — Timeout explícito en las llamadas al cliente de Anthropic
**Categoría:** `[RENDIMIENTO]` (también seguridad de disponibilidad) · **Beneficio:** Medio · **Esfuerzo:** 0,75h

- **Objetivo:** pasar un `timeout` explícito y corto (p. ej. 30-45s) al construir `anthropic.Anthropic(api_key=api_key)` en `ai_analyst.py:148` y `ai_generator.py:500`, dentro del mismo bloque `try/except` ya existente.
- **Beneficio:** con el servidor de desarrollo de Flask monoproceso, una llamada colgada a la API de Anthropic bloquea indefinidamente al único worker disponible — un timeout explícito acota el peor caso.
- **Riesgo:** bajo — el manejo de error ya existe (`except anthropic.APIError`), solo se acota su duración máxima.
- **Archivos afectados:** `analyzer/ai_analyst.py`, `analyzer/ai_generator.py`.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** revisar que el timeout está declarado explícitamente (no solo confiar en el default del SDK) y que, si se simula una llamada que excede el timeout (o se reduce temporalmente a 1s en local para probar), el flujo cae correctamente por la rama de error ya existente sin colgar el proceso.
- **¿Rompe compatibilidad?** No.

### 10 — Eliminar código muerto confirmado + import no usado
**Categoría:** `[DEUDA]` · **Beneficio:** Medio · **Esfuerzo:** 1h

- **Objetivo:** eliminar `compute_chain_effects()` (`chain_effects.py:331`, distinta de `compute_chain_effects_for_unit`, que sí se usa), `build_rooms()` (`parser.py:217`), `render_spatial_quality_legend_html()` (`spatial_quality.py:448`) y la constante `MIN_CORRIDOR_WIDTH_M` (`evaluator.py:730`); eliminar el import no usado de `UnitScore` en `reporter.py:15`.
- **Beneficio:** reduce la superficie del código a lo que realmente se ejecuta — cada función muerta es una pregunta futura sin respuesta clara sobre si se puede tocar o no.
- **Riesgo:** bajo. Antes de borrar, confirmar con una búsqueda global (no solo en `analyzer/`, también en `static/index.html` por si algo se referencia solo desde el JSON/nombre de función) que efectivamente no se usan — ya verificado en esta auditoría, pero repetir la comprobación antes de borrar es buena práctica.
- **Archivos afectados:** `analyzer/chain_effects.py`, `analyzer/parser.py`, `analyzer/spatial_quality.py`, `analyzer/evaluator.py`, `analyzer/reporter.py`.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** `ruff check` (regla `F401`) y `vulture` no vuelven a reportar estos símbolos; la aplicación arranca y un análisis completo (DXF real + proyecto generado + PDF) sigue funcionando igual que antes.
- **¿Rompe compatibilidad?** No — por definición, código que no se llama desde ningún sitio no puede romper nada al desaparecer.

### 11 — Corregir adyacencia acústica inerte (Bug #2)
**Categoría:** `[BUG]` · **Beneficio:** Alto · **Esfuerzo:** 1,5h

- **Objetivo:** sustituir la comprobación de intersección literal de `evaluator._is_adjacent` por la misma tolerancia de distancia ya validada en `circulation._rooms_are_connected` (`WALL_GAP_TOLERANCE_M`), para que el Bloque 16 (dormitorio junto a baño/aseo sin aislamiento verificado) pueda dispararse sobre datos reales.
- **Beneficio:** activa una regla normativa que hoy, con toda probabilidad, no se ha disparado nunca sobre un plano real desde que existe.
- **Riesgo:** medio. Es un cambio de comportamiento real: habitaciones que hoy nunca generan este aviso empezarán a generarlo si están realmente adyacentes. Puede aumentar de golpe el número de avisos IMPORTANTE en informes ya generados antes — mismo patrón de "salto esperado" que ya ocurrió al introducir el Bloque 19 sobre el Bloque 15 (documentado en el propio proyecto).
- **Archivos afectados:** `analyzer/evaluator.py` (`_is_adjacent`, `_shared_edge_length` o su reemplazo).
- **Dependencias:** ninguna técnica, pero se recomienda hacerla **después** de tener el test golden-master (tarea 18) para poder cuantificar exactamente cuánto cambia el resultado sobre `ejemplo.dxf` antes de darla por buena.
- **Cómo comprobar que ha quedado bien:** ejecutar el análisis sobre `ejemplo.dxf` y confirmar que al menos una de las unidades con dormitorio y baño/aseo genuinamente contiguos (gap ≤0,38m, ya documentado en el proyecto) genera ahora el aviso de adyacencia acústica, cosa que no ocurría antes.
- **¿Rompe compatibilidad?** No en el contrato de API. Sí cambia el número de issues devueltos (más avisos IMPORTANTE que antes) — comportamiento correcto, no un bug nuevo.

### 12 — Fijar versiones exactas de dependencias
**Categoría:** `[SEGURIDAD]` (reproducibilidad) · **Beneficio:** Medio · **Esfuerzo:** 1h

- **Objetivo:** congelar `requirements.txt` a las versiones exactas que funcionan hoy (`pip freeze` dentro del venv actual, filtrado a las 5 dependencias directas + sus transitivas relevantes), en vez de `>=` sin límite superior.
- **Beneficio:** una instalación nueva dentro de unos meses no puede romperse por un cambio de versión del SDK de Anthropic (que cambia con frecuencia) u otra dependencia.
- **Riesgo:** bajo — es fijar lo que ya funciona, no cambiar versiones.
- **Archivos afectados:** `requirements.txt`.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** crear un venv nuevo desde cero, `pip install -r requirements.txt`, ejecutar `app.py` y confirmar que arranca y analiza `ejemplo.dxf` sin errores de import ni de versión.
- **¿Rompe compatibilidad?** No.

### 13 — `debug=False` + servidor WSGI real (waitress)
**Categoría:** `[SEGURIDAD]` · **Beneficio:** Alto · **Esfuerzo:** 1,5h

- **Objetivo:** sustituir `app.run(debug=True, port=5000)` por un arranque condicionado a una variable de entorno (`FLASK_DEBUG=1` solo en local) y, para cualquier ejecución que no sea desarrollo puro, servir la app con `waitress` (funciona en Windows, a diferencia de `gunicorn`) en vez del servidor de desarrollo de Flask.
- **Beneficio:** elimina el depurador interactivo de Werkzeug (riesgo de ejecución remota de código si el puerto queda expuesto) y quita el techo artificial de "un usuario a la vez" del servidor de desarrollo.
- **Riesgo:** medio — cambia cómo se arranca la app; hay que asegurarse de que Pablo sigue pudiendo desarrollar en local con autorecarga cuando la quiera (vía la variable de entorno).
- **Archivos afectados:** `app.py` (bloque `if __name__ == "__main__":`), `requirements.txt` (añadir `waitress`), nuevo script o instrucción de arranque documentada.
- **Dependencias:** ninguna técnica; conviene hacerla después de la tarea 3 (`.env.example`) para documentar la nueva variable de entorno en el mismo sitio.
- **Cómo comprobar que ha quedado bien:** arrancar con `waitress-serve` (o el script equivalente) y confirmar que la SPA funciona igual que con `python app.py`; confirmar que sin `FLASK_DEBUG=1` el depurador de Werkzeug no aparece ante un error forzado.
- **¿Rompe compatibilidad?** No para el usuario final (misma URL, mismo comportamiento); sí cambia el comando que Pablo usa para arrancar la app en desarrollo si no exporta la variable de entorno.

### 14 — Consolidar el bucle de polígono-a-SVG duplicado 3 veces
**Categoría:** `[DEUDA]` · **Beneficio:** Medio · **Esfuerzo:** 1h

- **Objetivo:** extraer el bucle `" ".join(f"{sx:.2f},{sy:.2f}" ... zip(xs, ys))`, hoy copiado igual en `circulation.py:464`, `plan_svg.py:555` y `spatial_quality.py:420`, a una única función pública en `plan_svg.py` (que ya es la casa natural de la lógica de geometría-a-SVG, y ya la reutilizan los otros dos módulos para otras cosas).
- **Beneficio:** un solo sitio donde corregir esta lógica en el futuro (por ejemplo, si la tarea 7 requiere ajustar cómo se maneja una discrepancia de longitud) en vez de tres.
- **Riesgo:** bajo — extracción mecánica, sin cambio de comportamiento si se hace bien.
- **Archivos afectados:** `analyzer/plan_svg.py` (nueva función pública), `analyzer/circulation.py`, `analyzer/spatial_quality.py` (sustituir por la llamada compartida).
- **Dependencias:** se recomienda hacerla **después** de la tarea 7 (`zip` con `strict=`), para no duplicar el mismo trabajo dos veces sobre el mismo bucle.
- **Cómo comprobar que ha quedado bien:** generar el SVG de una misma vivienda antes y después del cambio y comparar el string resultante byte a byte — debe ser idéntico.
- **¿Rompe compatibilidad?** No.

### 15 — Timestamps con zona horaria
**Categoría:** `[BUG]` (menor) · **Beneficio:** Bajo · **Esfuerzo:** 0,5h

- **Objetivo:** sustituir `datetime.today()` (`pdf_report.py:88`) y `datetime.now()` (`reporter.py:325`) por versiones con zona horaria explícita (`datetime.now(tz=...)`, usando `Europe/Madrid` o UTC según se prefiera mostrar).
- **Beneficio:** corrección de bajo impacto hoy (un solo usuario en Madrid), pero elimina una fuente de fechas incorrectas en cuanto haya usuarios o servidores en otra zona horaria.
- **Riesgo:** ninguno.
- **Archivos afectados:** `analyzer/pdf_report.py`, `analyzer/reporter.py`.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** generar un PDF y un informe HTML y confirmar que la fecha mostrada sigue siendo correcta en hora local de Madrid.
- **¿Rompe compatibilidad?** No.

### 16 — Cutover final de `classify_problems` a tabla declarativa
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Alto · **Esfuerzo:** 1,5h

- **Objetivo:** una vez migrados todos los bloques (tareas 22-24), eliminar el código imperativo antiguo de `classify_problems`, dejar la función reducida a "recorrer la tabla declarativa y construir `IssueReport`", y confirmar que el resultado es idéntico al original.
- **Beneficio:** es el momento en que se materializa todo el beneficio de la refactorización más importante del proyecto — `classify_problems` pasa de 327 líneas/complejidad 49 a una función corta y un dato declarativo fácil de extender.
- **Riesgo:** medio-alto si se hace sin red de seguridad — por eso depende explícitamente del test golden-master.
- **Archivos afectados:** `analyzer/evaluator.py`.
- **Dependencias:** requiere las tareas 18 (test golden-master), 22, 23 y 24 completadas antes.
- **Cómo comprobar que ha quedado bien:** el test golden-master pasa sin cambios sobre `ejemplo.dxf` y sobre los casos sintéticos de tipología/zona añadidos en la tarea 18; `ruff check` confirma que la complejidad ciclomática de `classify_problems` ha bajado muy por debajo de 10.
- **¿Rompe compatibilidad?** No en el JSON de salida (ese es exactamente el criterio de éxito).

### 17 — README.md de arranque
**Categoría:** `[DX]` · **Beneficio:** Medio · **Esfuerzo:** 1,5h

- **Objetivo:** documentar cómo instalar el venv, qué variables de entorno hacen falta, cómo arrancar `app.py` (producto real) frente a `main.py` (herramienta de depuración interna, tras la tarea 4), y la convención de capas/colores que espera el parser DXF (`"00 areas"`, ACI 10/150).
- **Beneficio:** hoy nadie que no sea Pablo puede arrancar el proyecto sin adivinar estas cuatro cosas — bloqueante para incorporar a cualquier colaborador o para que un cliente técnico evalúe el código.
- **Riesgo:** ninguno.
- **Archivos afectados:** nuevo `README.md`.
- **Dependencias:** tiene más sentido hacerla después de las tareas 3, 4 y 13, para documentar el estado ya limpio en vez de documentar y tener que corregirlo después.
- **Cómo comprobar que ha quedado bien:** alguien que no haya tocado el proyecto (o una sesión nueva de este mismo asistente) puede arrancarlo siguiendo solo el README, sin preguntar nada más.
- **¿Rompe compatibilidad?** No.

### 18 — Suite de test golden-master
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Alto · **Esfuerzo:** 2h

- **Objetivo:** con `pytest`, crear un test que ejecute el pipeline completo sobre `ejemplo.dxf` (parser → evaluator → api_serializer) en al menos 3 escenarios (tipología/ciudad por defecto; `unifamiliar` + ciudad de zona D; `rehabilitacion` + ciudad de zona A), guarde el JSON resultante como fichero de referencia (`tests/fixtures/*.json`) y compare cualquier ejecución futura contra ese fichero.
- **Beneficio:** es la precondición real para poder tocar `evaluator.py` (2.966 líneas, 40 reglas) sin miedo — hoy cualquier cambio de umbral puede alterar otro bloque en silencio, sin que nada lo detecte. Habilita directamente las tareas 16, 22, 23, 24, 28 y 29.
- **Riesgo:** bajo en sí misma (solo añade tests); el riesgo real es generar el primer snapshot **antes** de corregir el Bug #1 (tarea 5) y congelar el bug como si fuera el comportamiento correcto.
- **Archivos afectados:** nuevo directorio `tests/`, nuevo `pytest` como dependencia de desarrollo.
- **Dependencias:** debe ejecutarse **después** de la tarea 5 (Bug #1) para que el snapshot de referencia capture el comportamiento ya corregido, no el bug.
- **Cómo comprobar que ha quedado bien:** `pytest` se ejecuta en verde localmente; modificar deliberadamente un umbral de una regla (p. ej. `MAX_ASPECT_RATIO`) y confirmar que el test falla — si no falla, el test no está comprobando lo que debería.
- **¿Rompe compatibilidad?** No.

### 19 — Reducir los 19 parámetros de `serialize_analysis`
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Alto · **Esfuerzo:** 2h

- **Objetivo:** agrupar los parámetros de contexto de proyecto (`edificio`, `superficie_solar_m2`, `normativa`, `proyecto`, `solar`) y los de resultados de edificio (`solar_occupation`, `buildability`, `max_floors`, `compactness`, `building_orientation`, `retranqueos`, `ceiling_height`) de `api_serializer.serialize_analysis` en 1-2 dataclasses (p. ej. `ProjectContext` y `BuildingResults`), reduciendo la firma de la función a un puñado de argumentos.
- **Beneficio:** además de mejorar la legibilidad, esto **previene directamente la próxima versión del Bug #1**: hoy es fácil olvidar pasar uno de 19 argumentos opcionales sin que nada avise; con una dataclase explícita, olvidar un campo obligatorio falla en el momento de construir el objeto, no en silencio dentro de un `.get()` con valor por defecto.
- **Riesgo:** medio — toca los dos call sites en `app.py` (`analizar` y `generar`) y la firma pública de `serialize_analysis`. Fácil de verificar con el test golden-master ya en marcha.
- **Archivos afectados:** `analyzer/api_serializer.py`, `app.py`.
- **Dependencias:** requiere la tarea 18 (test golden-master) para verificar con confianza que el JSON de salida no cambia; tiene sentido hacerla después de la tarea 5, para no reducir la firma de una función que todavía tiene el bug de argumentos olvidados.
- **Cómo comprobar que ha quedado bien:** el test golden-master pasa igual que antes; los dos endpoints (`/api/analizar`, `/api/generar`) devuelven el mismo JSON que antes del cambio sobre los mismos inputs.
- **¿Rompe compatibilidad?** No en el JSON de salida. Sí cambia la firma interna de `serialize_analysis` — solo afecta a quien la llame desde Python (hoy, únicamente `app.py`).

### 20 — Vendorizar `three.js` localmente
**Categoría:** `[SEGURIDAD]`/`[DEUDA]` · **Beneficio:** Medio · **Esfuerzo:** 1,5h

- **Objetivo:** descargar la build exacta de `three.js` r160 (y sus `examples/jsm` usados) y servirla desde `static/vendor/three/` en vez de cargarla en tiempo de ejecución desde `unpkg.com`, actualizando el import map de `static/index.html`.
- **Beneficio:** el visor 3D — una de las piezas más vistosas del producto en una demo — deja de depender de que una CDN externa esté disponible en el momento exacto de la demo, y funciona sin conexión a internet.
- **Riesgo:** bajo — es sustituir una URL remota por una local, sin tocar el código que usa `THREE.*`.
- **Archivos afectados:** `static/index.html` (import map), nuevos ficheros estáticos en `static/vendor/`.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** desconectar la máquina de internet (o bloquear `unpkg.com` en el `hosts`) y confirmar que el visor 3D de un proyecto generado sigue funcionando igual.
- **¿Rompe compatibilidad?** No.

### 21 — Eliminar la triple recomputación de `room_problems()`
**Categoría:** `[RENDIMIENTO]` · **Beneficio:** Medio · **Esfuerzo:** 1,5h

- **Objetivo:** `room_problems()` se llama hoy 3 veces por habitación en la misma petición (`api_serializer.py:71`, `api_serializer.py:227`, `plan_svg.py:546`). Calcularlo una sola vez por par (habitación, vivienda) y reutilizar el resultado en los tres sitios.
- **Beneficio:** reduce trabajo redundante que escala linealmente mal con el número de habitaciones — relevante en cuanto se analicen edificios grandes con muchas viviendas.
- **Riesgo:** medio — hay que enhebrar el resultado ya calculado a través de dos módulos (`api_serializer.py` y `plan_svg.py`) sin romper el orden de cálculo actual (algunos de estos sitios se ejecutan en momentos distintos del pipeline).
- **Archivos afectados:** `analyzer/api_serializer.py`, `analyzer/plan_svg.py`.
- **Dependencias:** conviene hacerla después de la tarea 18 (test golden-master) para verificar con confianza que ningún overlay de problemas en el SVG cambia.
- **Cómo comprobar que ha quedado bien:** el test golden-master pasa igual que antes; comparar el SVG generado antes y después del cambio para una misma vivienda — debe ser idéntico.
- **¿Rompe compatibilidad?** No.

### 22 — Diseño del motor de tabla declarativa para `classify_problems`
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Medio · **Esfuerzo:** 2h

- **Objetivo:** diseñar la estructura de datos (p. ej. una lista de `IssueRule(campo_resultado, severidad, bloque, codigo, titulo, impacto, solucion, condicion_opcional)`) y la función genérica que la recorre y construye `IssueReport` a partir de `AdvancedAnalysis`/`UnitScore`, **sin** todavía migrar ningún bloque real — se desarrolla y se prueba en paralelo al código imperativo existente, sin sustituirlo aún.
- **Beneficio:** sienta la base para que las tareas 23 y 24 sean migraciones mecánicas de bajo riesgo en vez de una reescritura monolítica de 327 líneas de una sola vez.
- **Riesgo:** bajo — no toca el camino de código que hoy está en producción, es una pieza nueva y aislada.
- **Archivos afectados:** `analyzer/evaluator.py` (nueva sección, sin cablear todavía a `classify_problems`).
- **Dependencias:** requiere la tarea 18 (test golden-master) como red de seguridad para las tareas siguientes que sí modifican el camino real.
- **Cómo comprobar que ha quedado bien:** un test unitario aislado del motor nuevo, con 2-3 reglas de ejemplo migradas a mano, produce el mismo `IssueReport` que produciría el código imperativo equivalente.
- **¿Rompe compatibilidad?** No — código nuevo sin cablear todavía.

### 23 — Migrar bloques CRITICO a la tabla declarativa
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Medio · **Esfuerzo:** 2h

- **Objetivo:** migrar los ~6 bloques de severidad CRITICO de `classify_problems` (superficie útil insuficiente, baño sin espacio de giro, dormitorio bajo mínimo, baño adaptado, pasillo estrecho, evacuación excesiva, espacio de giro de baño) a la tabla declarativa de la tarea 22, dejando el código imperativo original comentado o en paralelo hasta el cutover final.
- **Beneficio:** reduce ~90 líneas de código repetitivo por una estructura de datos equivalente y más fácil de auditar de un vistazo.
- **Riesgo:** medio — cada bloque migrado debe producir exactamente el mismo `IssueReport` que el original (mismo `bloque`, `codigo`, `titulo`, `impacto`, `solucion`).
- **Archivos afectados:** `analyzer/evaluator.py`.
- **Dependencias:** requiere la tarea 22 completada; requiere la tarea 18 (test golden-master) para verificar equivalencia bloque a bloque.
- **Cómo comprobar que ha quedado bien:** ejecutar ambos caminos (imperativo y declarativo) en paralelo sobre `ejemplo.dxf` durante la migración y diferenciar sus salidas — deben ser idénticas antes de continuar.
- **¿Rompe compatibilidad?** No, si la verificación de equivalencia se hace correctamente antes de avanzar.

### 24 — Migrar bloques IMPORTANTE a la tabla declarativa
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Medio · **Esfuerzo:** 2h

- **Objetivo:** migrar los ~13 bloques de severidad IMPORTANTE (condensaciones, itinerario accesible, luz natural, proporción, jerarquía, profundidad, factor de luz, huecos 1/8, ventilación cruzada, adyacencia acústica, exposición acústica, anchura mínima, ratio de baños, distancia de entrada) siguiendo el mismo patrón que la tarea 23. Los bloques RECOMENDACION y de edificio (más cortos, ~10 bloques) se incluyen aquí o se reparten en una continuación de esta misma tarea si el tiempo se ajusta.
- **Beneficio:** completa la migración del grueso de `classify_problems`, dejando solo el cutover final (tarea 16).
- **Riesgo:** medio, mismo patrón que la tarea 23 — es el bloque con más reglas (mayor superficie de posible error de transcripción de textos/códigos).
- **Archivos afectados:** `analyzer/evaluator.py`.
- **Dependencias:** requiere las tareas 22 y 23 completadas.
- **Cómo comprobar que ha quedado bien:** mismo criterio que la tarea 23 — comparación exhaustiva de ambos caminos sobre `ejemplo.dxf` y sobre los escenarios sintéticos de tipología/zona del test golden-master.
- **¿Rompe compatibilidad?** No, con la misma condición que la tarea 23.

### 25 — Consolidar adyacencia duplicada (`evaluator` ↔ `circulation`)
**Categoría:** `[DEUDA]` · **Beneficio:** Bajo · **Esfuerzo:** 1h

- **Objetivo:** una vez corregida `evaluator._is_adjacent` (tarea 11) con la misma tolerancia de distancia que `circulation._rooms_are_connected`, evaluar si `circulation.py` puede reutilizar directamente la función de `evaluator.py` en vez de mantener una segunda implementación equivalente.
- **Beneficio:** un único punto de verdad para "¿estas dos habitaciones son adyacentes?" en todo el proyecto.
- **Riesgo:** bajo — ambas funciones, tras la tarea 11, deberían ser equivalentes; el riesgo está en confirmarlo con datos reales antes de eliminar una de las dos.
- **Archivos afectados:** `analyzer/circulation.py`, `analyzer/evaluator.py`.
- **Dependencias:** requiere la tarea 11 completada.
- **Cómo comprobar que ha quedado bien:** el test golden-master y las salidas de `circulation.py` sobre `ejemplo.dxf` no cambian tras la consolidación.
- **¿Rompe compatibilidad?** No.

### 26 — Benchmark de `compute_puntos_ganados` (O(n²))
**Categoría:** `[RENDIMIENTO]` · **Beneficio:** Bajo · **Esfuerzo:** 1h

- **Objetivo:** escribir un test/script que genere sintéticamente 200-300 `IssueReport` (más issues de las que produciría cualquier proyecto real hoy) y mida el tiempo de `compute_puntos_ganados`, para decidir con datos si el algoritmo O(n²) documentado por el propio autor necesita optimizarse ahora o puede esperar.
- **Beneficio:** evita tanto el riesgo de un cuello de botella no detectado en proyectos grandes como el riesgo opuesto — optimizar prematuramente algo que en la práctica es intrascendente.
- **Riesgo:** ninguno — es solo medición, sin cambiar código de producto (salvo que el resultado justifique abrir una tarea de optimización aparte, fuera de este plan).
- **Archivos afectados:** ninguno de producto; nuevo script/test de benchmark.
- **Dependencias:** ninguna.
- **Cómo comprobar que ha quedado bien:** el benchmark se ejecuta y deja documentado (en un comentario o en el propio test) el tiempo medido a 300 issues, con un veredicto explícito ("aceptable hasta X issues" o "requiere optimización, ver tarea futura").
- **¿Rompe compatibilidad?** No.

### 27 — Limpieza mecánica `PERF401` + parámetro `unit` sin usar
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Bajo · **Esfuerzo:** 1h

- **Objetivo:** aplicar la corrección automática de `ruff` (`--fix`) a los 35+ casos de `PERF401` (bucles manuales de `append` reemplazables por comprensión de lista o `list.extend`) en `evaluator.py` y `plan_svg.py`; revisar y documentar (o eliminar si procede) el parámetro `unit` sin usar de `evaluate_acoustic_exposure` (`evaluator.py:1431`).
- **Beneficio:** código más idiomático y ligeramente más rápido; cierra los últimos hallazgos de estilo/calidad de la auditoría estática.
- **Riesgo:** bajo — son transformaciones mecánicas marcadas por `ruff` como seguras (`--fix`, no `--unsafe-fixes`).
- **Archivos afectados:** `analyzer/evaluator.py`, `analyzer/plan_svg.py`.
- **Dependencias:** requiere la tarea 8 (`pyproject.toml` con `ruff`) para tener la configuración ya establecida; conviene hacerla después del cutover de `classify_problems` (tarea 16), ya que varios `PERF401` viven precisamente en los bloques que esa refactorización va a eliminar.
- **Cómo comprobar que ha quedado bien:** `ruff check` deja de reportar `PERF401`; el test golden-master sigue en verde.
- **¿Rompe compatibilidad?** No.

### 28 — Extraer modelos/dataclasses de `evaluator.py`
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Bajo · **Esfuerzo:** 2h

- **Objetivo:** mover las dataclasses de dominio (`Unit`, `UnitScore`, `AdvancedAnalysis`, `RuleResult`, `IssueReport` y los ~35 `*Result` de cada regla) a un módulo `analyzer/models.py`, dejando `evaluator.py` centrado solo en las funciones `evaluate_*`.
- **Beneficio:** primer paso hacia deshacer el "módulo que hace demasiadas cosas" (`evaluator.py`, 2.966 líneas) sin tocar ninguna lógica, solo organización.
- **Riesgo:** medio — toca imports en casi todos los módulos de `analyzer/` (`circulation.py`, `spatial_quality.py`, `chain_effects.py`, `scoring.py`, `api_serializer.py`, `plan_svg.py`, `reporter.py`, `pdf_report.py`) y en `app.py`/`main.py`. El riesgo no es de lógica, es de olvidar actualizar un import y romper el arranque.
- **Archivos afectados:** todos los anteriores (solo la línea de import en la mayoría de ellos).
- **Dependencias:** requiere la tarea 18 (test golden-master); se recomienda hacerla **después** del cutover de `classify_problems` (tarea 16), para no reorganizar un archivo que todavía va a cambiar de tamaño significativamente.
- **Cómo comprobar que ha quedado bien:** la aplicación arranca (`python app.py`), el test golden-master pasa, y `python -c "import app"` no lanza `ImportError`.
- **¿Rompe compatibilidad?** No en comportamiento; si algún día hay código externo importando directamente `analyzer.evaluator.Unit` (hoy no lo hay, verificado), tendría que actualizar la ruta de import.

### 29 — Extraer reglas de urbanismo de edificio a su propio módulo
**Categoría:** `[MANTENIBILIDAD]` · **Beneficio:** Bajo · **Esfuerzo:** 1,5h

- **Objetivo:** mover `evaluate_solar_occupation`, `evaluate_buildability`, `evaluate_max_floors`, `evaluate_retranqueos`, `evaluate_building_compactness`, `evaluate_building_orientation_ratio`, `evaluate_ceiling_height`, `compute_floor_areas` y `compute_floor_perimeter_m` (todas las reglas "de edificio", no de vivienda/habitación) a `analyzer/urbanismo.py`.
- **Beneficio:** segundo paso de desmontar el módulo gigante; separa con claridad "reglas de vivienda" de "reglas de edificio completo", que hoy conviven en el mismo archivo sin ninguna frontera visible.
- **Riesgo:** bajo-medio — menos puntos de import afectados que la tarea 28 (`app.py` es el principal consumidor).
- **Archivos afectados:** `analyzer/evaluator.py` (o `analyzer/urbanismo.py` tras la extracción), `app.py`.
- **Dependencias:** requiere la tarea 18 (test golden-master); tiene sentido hacerla después de la tarea 28, para no mover código dos veces.
- **Cómo comprobar que ha quedado bien:** mismo criterio que la tarea 28 — arranque limpio y test golden-master en verde.
- **¿Rompe compatibilidad?** No, con la misma salvedad que la tarea 28.

---

## Las 10 tareas que más valor añaden por menos esfuerzo

Si solo hay tiempo para una sesión de trabajo corta, este es el subconjunto con mayor retorno inmediato — en orden:

1. **Tarea 1** — Confirmar en git el trabajo pendiente (15 min, evita una pérdida catastrófica).
2. **Tarea 2** — Etiquetar el percentil como estimación (30 min, cierra un riesgo reputacional real).
3. **Tarea 3** — `.env.example` (15 min, trivial).
4. **Tarea 4** — Retirar ruta personal + banner de CLI en desuso (30 min, evita una vergüenza fácil de evitar).
5. **Tarea 5** — Corregir el Bug #1 de tipología/zona climática (1,5h, es el fallo funcional más grave de todo el producto).
6. ~~**Tarea 7** — `zip()` con `strict=`~~ **hecha (ver Apéndice A.2, corrección 2026-08-20)** — no queda trabajo aquí.
7. **Tarea 8** — `pyproject.toml` con `ruff` (45 min, congela todo lo aprendido en esta auditoría para que no vuelva a pasar).
8. **Tarea 9** — Timeout en el cliente de Anthropic (45 min, evita que una llamada colgada tumbe el único worker disponible).
9. **Tarea 10** — Eliminar código muerto confirmado (1h, reduce ruido con riesgo cero).
10. **Tarea 12** — Fijar versiones de dependencias (1h, evita una rotura futura sin ningún coste hoy).

Con estas 10 tareas (≈8 horas en total) el proyecto pasa de "prototipo con un bug crítico activo y sin red de seguridad" a "prototipo honesto, correcto en su flujo principal, y protegido contra las roturas más obvias" — sin haber tocado todavía ni una línea de la refactorización estructural grande (tareas 16-24, ~14h adicionales), que sigue siendo necesaria antes de escalar el equipo o el volumen de clientes, pero que ya no compite por ser la primera prioridad.

---

# APÉNDICE A — Estado real y plan de fases (auditoría de 2026-08-18)

**Este apéndice manda sobre el cuerpo del documento.** Lo de arriba se escribió el 2026-07-31 y su primera afirmación —*"Ninguna tarea de este documento se ha implementado todavía"*— dejó de ser cierta hace tiempo. Lo que sigue es el resultado de contrastar las 29 tareas, una por una, contra el código real del repositorio, no contra el propio documento.

## A.1 — Por qué las estimaciones de arriba ya no valen

El plan describe un código que ya no existe con esa forma:

| | En el documento (2026-07-31) | Medido el 2026-08-18 |
|---|---:|---:|
| Módulos en `analyzer/` | 15 | **43** |
| Líneas en `analyzer/` | ~7.700 | **18.680** |
| `evaluator.py` | 2.966 | **3.503** |
| `classify_problems` | 327 líneas | **383** |
| Frontend | 1 fichero, 5.313 líneas | **14 ficheros, 15.460 líneas** |
| Tests | ninguno | **97 ficheros + 9 goldens** |

Paquetes que no existían y que el plan no contempla: `modelo/`, `normativa/`, `ingesta/`, `analyzer/interview/`. **Ninguno invalida ninguna tarea** — pero varias las hacen más urgentes (más código detrás de `evaluator.py`, más clientes de Anthropic sin timeout, más CDNs externas). Reestimar antes de atacar cualquiera de las tareas grandes.

## A.2 — Estado de las 29 tareas

Resumen original de la auditoría: **6 resueltas · 3 parciales · 20 pendientes.** Tras las Fases 1 y 2 (2026-08-18): **13 hechas o resueltas · 1 parcial · 15 pendientes**, y de esas 15 hay 2 descartadas (las tareas 15 y 26, ver A.4).

**Corrección (2026-08-20), verificada contra el código real, no contra este documento — mismo patrón de error que el de `three.js` en el diagnóstico estratégico del mismo día (`docs/design/2026-08-20-reorientacion-estrategica-v1.md`):** tres filas de la tabla estaban desactualizadas. **17 hechas o resueltas · 12 pendientes** tras esta corrección.

- **Tarea 7** (`zip()` con `strict=`) pasa de PENDIENTE a **RESUELTA**: los dos sitios que lo necesitaban (`app.py:708`, `plan_svg.py:285`) ya lo llevan, con comentario `(tarea 7)`. Los tres restantes (`evaluator.py:586`, `ocupacion.py:589`, `sectorizacion.py:287`) llevan un comentario `zip-sin-strict` explicando por qué `strict=True` sería incorrecto ahí (pares consecutivos de largos distintos por definición, o largos ya validados con un mensaje de error mejor). No es que falte hacerlo: ya se decidió, caso por caso, y quedó escrito en el propio código.
- **Tarea 10** (código muerto) pasa de PARCIAL a **RESUELTA**: `scoring.estimar_percentil` ya no existe en ningún fichero (se eliminó junto con el percentil comparativo, no solo quedó sin llamadores). `evaluator._is_adjacent` tampoco existe — sólo queda una mención en un comentario explicando el cambio de criterio. (Hay un `_is_adjacent` distinto y sí usado en `analyzer/ai_generator.py:757`; el documento original lo confundía con el de `evaluator.py`.)
- **Tarea 20** (vendorizar `three.js`) pasa de "PENDIENTE Y AGRAVADA" a **HECHA**: `static/vendor/three/`, `static/vendor/threebox/`, `static/vendor/mapbox-gl/`, `static/vendor/fuentes/` y `static/vendor/leaflet/` existen, con manifiesto y README propios (`static/vendor/vendorizar.py`, `static/vendor/MANIFEST.json`). El único CDN que queda vivo a propósito es el servicio de mapas (Mapbox/ArcGIS, datos en vivo, no código ejecutable) — riesgo distinto y menor, no una CDN de librería sin vendorizar.

Las tareas 8, 14, 19, 21, 22-24, 27, 28 y 29 se re-verificaron el mismo día y **siguen genuinamente pendientes tal como las describe la tabla** (evidencia re-confirmada línea por línea contra el código actual, no sólo releída).

| # | Tarea | Estado | Evidencia |
|---|---|---|---|
| 1 | Confirmar en git el trabajo pendiente | **RESUELTA** | Árbol limpio; los 113 commits de `shell-lateral-inicio` absorbidos en `main` |
| 2 | Etiquetar el percentil como estimación | **RESUELTA** (por eliminación) | El percentil se retiró del payload y de la SPA (`static/app.js:3816`); `test_scoring_coherencia.py:192` lo verifica. Deja `scoring.estimar_percentil` sin llamadores |
| 3 | `.env.example` | **HECHA** (`1015275`) | Existe, con las 11 variables reales del proyecto, y se carga de verdad vía `analyzer/entorno.py` |
| 4 | Ruta personal hardcodeada | **HECHA** (`e74be5e`) | Los 9 sitios retirados. `ejemplo.dxf` derivado de la ubicación del fichero; `v2s.dxf` vía `ARCHMUSE_DXF_V2S` |
| 5 | `zona_cte`/`tipología` en `/api/analizar` | **RESUELTA** | `app.py:492-495`, `:507-509`, `:709-715` |
| 6 | Aviso de zona climática por defecto | **HECHA** (`ed0f373`) | `resolver_zona_cte()` devuelve `(zona, resuelta)`; el repliegue a `"C"` sigue igual pero sale como limitación. No se deduce de "la zona es C": Barcelona **es** zona C por dato |
| 7 | `zip()` con `strict=` | ~~PENDIENTE~~ **RESUELTA (2026-08-20)** | `app.py:708` y `plan_svg.py:285` ya lo llevan. Los 3 restantes documentan por qué no aplica (`zip-sin-strict`). Ver corrección arriba |
| 8 | `pyproject.toml` con `ruff` | PENDIENTE | Existe `pyproject.toml`, pero **solo con la configuración de pytest** (el propio fichero lo dice: "eso es la tarea 8... y es otra conversación"). `ruff` sigue sin instalar ni configurar. Re-verificado 2026-08-20 |
| 9 | Timeout en el cliente de Anthropic | **HECHA** (`0e2312c`) | Eran **seis**, no cinco: faltaba `extraccion/interprete.py:153`. Los seis pasan por `ia/cliente.py`, y `tests/test_anthropic_timeout.py` prohíbe construir el cliente fuera de ella |
| 10 | Eliminar código muerto | ~~PARCIAL~~ **RESUELTA (2026-08-20)** | `scoring.estimar_percentil` ya no existe en el repo. `evaluator._is_adjacent` tampoco. Ver corrección arriba |
| 11 | Adyacencia acústica inerte (Bug #2) | **RESUELTA** | `analyzer/adyacencia.py` + `tramo_enfrentado_m`; `tests/test_acoustic_adjacency.py` pasa 29/29 |
| 12 | Fijar versiones de dependencias | **HECHA** (`88acb90`) | Las 13 directas con `==`, y `requirements.lock.txt` con las 58 distribuciones. Verificado en un venv nuevo desde cero |
| 13 | `debug=False` + servidor WSGI | **HECHA** (`885dfde`) | `waitress` por defecto sobre 127.0.0.1; el depurador de Werkzeug solo con `FLASK_DEBUG=1` |
| 14 | Consolidar polígono→SVG | ~~PENDIENTE Y AGRAVADA~~ **HECHA (2026-08-20)** | `svg_points()` ya resolvía la conversión de un anillo (commit ya en main). Corrección (2026-08-20, madrugada): quedaba sin resolver el cálculo del propio `to_screen` (`scale`/`offset_x`/`offset_y`), copiado en los tres generadores. Extraído a `calcular_transformador_de_pantalla()` en `plan_svg.py`. Verificado con los goldens (SVG bit a bit idéntico) |
| 15 | Timestamps con zona horaria | PENDIENTE | `pdf_report.py:93`, `reporter.py:325` |
| 16 | Cutover de `classify_problems` | **PENDIENTE Y AGRAVADA** | 383 líneas (eran 327); 0 coincidencias de tabla declarativa |
| 17 | README de arranque | **HECHA** (`376fb4c`) | Cerradas las dos lagunas: convención de capas del DXF (contrato `AM_*` y modo heredado) y `app.py` frente a `main.py` |
| 18 | Suite golden-master | **HECHA** (`35f5a8d`) | G6 pasa de 1 escenario a 4 (por defecto, `unifamiliar`+zona D, `rehabilitacion`+zona A, municipio no reconocido) con un bloque `sensibilidad` que hace legible el diff. De paso: el G6 anterior leía `puntuacion`/`valoracion`, claves que el payload no tiene, así que congelaba `null` en los dos números más importantes de la API |
| 19 | Parámetros de `serialize_analysis` | **PENDIENTE Y AGRAVADA** | De 19 a **24**; sin dataclases |
| 20 | Vendorizar `three.js` | ~~PENDIENTE Y AGRAVADA~~ **HECHA (2026-08-20)** | `static/vendor/three/`, `/threebox/`, `/mapbox-gl/`, `/fuentes/`, `/leaflet/`, con manifiesto propio. Ver corrección arriba |
| 21 | Triple recomputación de `room_problems` | PENDIENTE | `api_serializer.py:78`, `:388`, `plan_svg.py:639` |
| 22-24 | Tabla declarativa (diseño + migración) | **PENDIENTE Y AGRAVADA** | No existe. Su estimación de 6 h se calculó sobre 327 líneas y ~19 bloques |
| 25 | Consolidar adyacencia duplicada | **RESUELTA** | `circulation.py:143-144` delega en `adyacencia.py` |
| 26 | Benchmark de `compute_puntos_ganados` | PENDIENTE — **descartada**, ver A.4 | No existe ningún benchmark |
| 27 | `PERF401` + parámetro `unit` sin usar | ~~PENDIENTE~~ **PARCIAL, mitad HECHA (2026-08-20)** | `unit` retirado de `evaluate_acoustic_exposure()` (`evaluator.py`) -- 0 usos en el cuerpo, 1 solo sitio de llamada, verificado antes de tocar la firma. `ruff` ya instalado (tarea 8): quedan 106 `PERF401` reales sin tocar, ver §A.2 |
| 28 | Extraer `models.py` | PENDIENTE | No existe `analyzer/models.py` |
| 29 | Extraer `urbanismo.py` | PENDIENTE | No existe; las 6 reglas de edificio siguen en `evaluator.py:3067-3430` |

## A.3 — Plan de fases

Sustituye al orden por ROI de la tabla resumen. El criterio ya no es el ROI aislado de cada tarea, sino qué desbloquea a qué.

### Fase 0 — Hacer ejecutable la verdad · **CERRADA el 2026-08-18**

El hallazgo que reordenó todo: **`pytest` no ejecutaba nada.** Abortaba la recolección con `INTERNALERROR` porque 72 de los 97 ficheros de `tests/` son scripts que se ejecutan al importarse y terminan en `sys.exit()`. El README decía que bastaba con `pytest`. No había forma de responder "¿está el proyecto en verde?".

Resuelto con `conftest.py`, `tests/test_scripts_legacy.py` y `pyproject.toml`, sin modificar ningún test existente. **De 0 tests recogidos a 360; de un `INTERNALERROR` a 357 passed / 3 xfailed / 0 failed en ~14 min.** Los 5 rojos que aparecieron se triaron uno a uno (ver el commit *"test: triaje de los 5 tests en rojo"*): tres eran tests caducados o fixtures en CRLF y se arreglaron; dos son el defecto H1 de `docs/audits/2026-08-13-hallazgos-cierre-geometrico.md` y quedan como `xfail(strict=True)` en `ROJOS_CONOCIDOS` (`conftest.py`), con motivo y referencia.

**Lo que compra esta fase:** que un rojo vuelva a significar algo. Sin ella, las tareas 16 y 19-29 se harían a ciegas — todas dependen, por escrito, de tener red de seguridad.

### Fase 1 — Lo que está publicado en internet · **CERRADA el 2026-08-18**

Tareas **13**, **4**, **3** y los dos huecos del README (tarea **17**). El repositorio es público: `debug=True` y la ruta personal de Pablo eran las dos cosas que tenía delante cualquiera que lo abriera.

| Tarea | Qué se hizo | Commit |
|---|---|---|
| **13** | Arranque con `waitress`; `debug=True` solo si `FLASK_DEBUG` lo pide. Elimina el depurador de Werkzeug (ejecución de código arbitrario desde el navegador) y el techo de una petición a la vez. | `885dfde` |
| **4** | Los 9 puntos con la carpeta personal del autor (`C:\Users\<usuario>\...`) fuera. `ejemplo.dxf` se deriva de la ubicación del fichero; `v2s.dxf` se localiza con `ARCHMUSE_DXF_V2S`. Banner de «esto no es el producto» en `main.py` y `analyzer/reporter.py`. | `e74be5e` |
| **3** | `.env.example` con las 11 variables reales del proyecto (la ficha pedía una), y carga efectiva vía `analyzer/entorno.py` desde `app.py`, `main.py` y `conftest.py`. | `1015275` |
| **17** | Convención de capas del DXF (contrato `AM_*` y modo heredado) y `app.py` frente a `main.py`, en el README. | `376fb4c` |

Dos desviaciones deliberadas de las fichas, ambas razonadas en su commit:

- **Tarea 4** — se mantuvo `python main.py` funcionando con un valor por defecto derivado, en vez de forzar el argumento obligatorio que pedía la ficha. El objetivo (que no haya la carpeta de nadie en un repositorio público) se cumple igual.
- **Tarea 17** — la ficha enunciaba la convención de color al revés («ACI 10/150» como lo que hay que dibujar). Lo correcto es `BYLAYER`; un color explícito es lo que marca un polígono como posible contorno agrupador descartable, y solo se descarta si además contiene otro polígono `BYLAYER` menor con la misma etiqueta.

**Lo que compra esta fase:** que el repositorio público deje de exponer una vulnerabilidad de ejecución remota y la carpeta personal de su autor, y que alguien distinto de Pablo pueda arrancarlo sin adivinar.

### Fase 2 — Blindar lo ya arreglado · **CERRADA el 2026-08-18**

Escenarios de tipología/zona en el golden G6 (cierra el hueco de la tarea 18 y protege por fin la corrección del Bug #1), y tareas **6**, **9**, **12**.

| Trabajo | Qué se hizo | Commit |
|---|---|---|
| **G6 multiescenario** (tarea 18) | De 1 escenario a 4: por defecto; `unifamiliar` + Madrid (zona D); `rehabilitacion` + Málaga (zona A); y Cuenca, municipio fuera de la tabla. Bloque `sensibilidad` con el canario `analisis_identico_al_defecto`. | `35f5a8d` |
| **6** | `resolver_zona_cte()` devuelve `(zona, resuelta)`; el repliegue a "C" sigue igual pero deja de ser silencioso: sale como limitación en el JSON. | `ed0f373` |
| **9** | Fachada `ia/cliente.py` con dos tramos de timeout (120 s / 300 s) sobre los **seis** clientes de Anthropic, y un test que prohíbe construir el cliente fuera de ella. | `0e2312c` |
| **12** | Las 13 dependencias directas con `==`, más `requirements.lock.txt` con las 58 distribuciones. | `88acb90` |

Tres desviaciones deliberadas de las fichas, todas razonadas en su commit:

- **Tarea 9** — la ficha pedía "30-45 s". Imposible: `ai_generator` pide 8.192 tokens de salida en una sola llamada y eso no cabe en 45 s a ninguna velocidad realista; el timeout "corto" no acotaría el peor caso, convertiría el caso normal en un fallo. Dos tramos calibrados por `max_tokens` en su lugar.
- **Tarea 12** — la ficha pedía fijar las directas "y sus transitivas relevantes". Elegir a mano cuáles son "relevantes" es adivinar, y fijar solo las directas no reproduce nada. Se separan los papeles: `requirements.txt` (de qué depende el producto, y por qué) y `requirements.lock.txt` (qué se instala exactamente).
- **Alcance de la 9** — la ficha hablaba de 2 clientes, la A.2 contó 5, y el test de guardia encontró un **sexto** que no estaba en ninguna de las dos listas: `extraccion/interprete.py`. Se arreglaron los seis.

**Lo que compra esta fase:** que romper otra vez el Bug #1 tenga consecuencias visibles, que un dato supuesto no se pueda confundir con un dato real, que una llamada colgada a Claude no retenga un hilo media hora, y que una instalación dentro de seis meses sea la misma que la de hoy.

**Hallazgo que esta fase no arregla, y conviene no perder:** `tests/canario.py` — la prueba de que los goldens siguen mordiendo, criterio A4 del PRD de E0 — **no se puede ejecutar hoy**. Medido, no supuesto: aborta en su línea base (`[FALLO] sin mutacion, 0 goldens rotos -- rotos: ['G9_modelo']`, salida 1) porque G9 ya falla por el defecto H1 de `docs/audits/2026-08-13-hallazgos-cierre-geometrico.md` §2, que se dejó sin corregir a propósito. Es anterior a esta fase y no lo causa nada de lo hecho aquí, pero significa que la única herramienta que demuestra que la red de seguridad funciona lleva parada desde entonces. Candidato a la Fase 3.

### Fase 3 — Reducir superficie

Tareas **10**, **7**, **14**, **20**. Con la suite ejecutable, la 7 deja de dar miedo.

### Fase 4 — La refactorización grande, reestimada

Tarea **19**, luego **22 → 23 → 24 → 16**, y al final **21**, **27**, **28**, **29**. No empezar sin reestimar (ver A.1).

## A.4 — Tareas descartadas

Ninguna es obsoleta; estas dos no merecen el tiempo hoy:

- **Tarea 26** (benchmark de `compute_puntos_ganados`) — mide un O(n²) sobre listas de issues que en la práctica no pasan de decenas. Optimización preventiva de un problema hipotético. Reabrir si alguien reporta lentitud.
- **Tarea 15** (timestamps con zona horaria) — correcta pero intrascendente con un único usuario en Madrid. Que caiga por arrastre cuando se toque `pdf_report.py` por otro motivo.

Y una advertencia de secuencia: **las tareas 28 y 29 no se tocan antes de la 16.** Mover 3.500 líneas de sitio antes de reducir `classify_problems` es reorganizar un fichero que va a cambiar de tamaño. Ya lo dice su propia ficha.

## A.5 — Lo que esta auditoría no pudo verificar

- **Cuántos de los 97 ficheros de test pasaban** antes de la Fase 0. Los códigos de salida no eran fiables y el barrido completo llevaba horas. Con `pytest` ya funcionando, la pregunta tiene respuesta en 14 minutos.
- **Los 35+ hallazgos `PERF401` de la tarea 27.** `ruff` no está instalado y la auditoría no instaló nada.
- **Cuándo se introdujo cada cosa.** La historia se aplastó en un commit al publicar el repositorio; no hay `git blame` útil anterior a esa fecha.
