# PRD — Gestor de proyectos y persistencia de sesión

**Estado:** Borrador · **Fecha:** 2026-08-01 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 1. Problema que resuelve

Hoy ArchMuse **no recuerda nada**. `POST /api/analizar` guarda el DXF en un `tempfile.TemporaryDirectory` que se destruye al terminar la petición (`app.py:66`), devuelve el JSON y olvida que el proyecto existió. No hay base de datos, no hay directorio de trabajo, no hay identificador de proyecto. La única persistencia del sistema es la pestaña del navegador abierta: recargar la página borra el análisis.

Consecuencias medibles hoy:

- **El arquitecto vuelve a subir el mismo DXF cada vez.** Es la fricción que Pablo señala explícitamente: "el usuario nunca debería tener que volver a subir el mismo DXF".
- **Cada re-subida vuelve a llamar a la API de Anthropic** (`analyze_with_ai`, `ai_analyst.py:130`, `max_tokens=4096`) aunque el archivo sea byte a byte idéntico y el resultado vaya a ser el mismo. Se paga dos veces por la misma respuesta y el usuario espera de nuevo.
- **No existe un "proyecto" como objeto de producto.** Existe "el análisis que estoy mirando ahora". Sin proyecto no hay historial, no hay comparación entre versiones de un plano, no hay nada a lo que volver mañana.

Esto es también el bloqueo estructural del rediseño de escritorio: una aplicación profesional se organiza alrededor de un documento que persiste. Sin persistencia, un árbol de proyecto, un menú "Guardar" o un panel "Mis proyectos" serían decorado sobre nada.

Enlaza con `NORTH_STAR_2031.md` (retención: el producto que se abre cada día, no el que se usa una vez) y con `MOAT_ANALYSIS.md`: el histórico acumulado de proyectos analizados es de los pocos activos de ArchMuse que un competidor no puede copiar clonando la funcionalidad.

## 2. Usuario afectado

El arquitecto individual o el estudio pequeño que hoy ya usa ArchMuse en local — el usuario real de hoy, no el objetivo de 2031. Es quien tiene el DXF en su disco, quien itera sobre el mismo plano varios días seguidos y quien paga los tokens.

No cubre el usuario multiusuario/estudio con equipo: este PRD asume **una sola persona en una sola máquina** (ver §14).

## 3. Objetivo de negocio

Tres efectos, por orden de importancia:

1. **Retención.** Un producto sin memoria se usa una vez. Con "Mis proyectos" hay una razón para volver a abrir la aplicación sin traer un archivo nuevo.
2. **Coste variable.** Reutilizar el análisis cacheado elimina llamadas duplicadas a la API. Es el único punto del sistema donde ahorrar dinero no cuesta calidad: la respuesta cacheada es idéntica a la que se pagaría.
3. **Base para todo lo demás.** Comparar dos versiones de un plano, medir si las recomendaciones se aplican, o cobrar por proyecto — todo requiere que el proyecto exista como entidad. Este PRD es la precondición, no una funcionalidad aislada.

## 4. Objetivo técnico

Una vez implementado debe ser cierto que:

- Analizar un DXF crea un **proyecto persistente** identificado de forma estable, que sobrevive a recargar la página, cerrar el navegador y reiniciar el servidor Flask.
- Abrir un proyecto existente devuelve el análisis completo **sin ejecutar el parser, sin recalcular la evaluación y sin llamar a la API de Anthropic**.
- Subir un DXF **cuyo contenido ya fue analizado con los mismos parámetros** reutiliza el análisis en vez de repetirlo.
- La aplicación restaura al abrir el estado de trabajo: vivienda seleccionada, modo activo y encuadre del plano.
- Nada de esto cambia el resultado del análisis: el JSON de un proyecto recién analizado y el de ese mismo proyecto reabierto son **idénticos byte a byte**.

## 5. Casos de uso

**CU-1 — Primer análisis.** El arquitecto arrastra `edificio-calle-mayor.dxf`, indica norte y ciudad, analiza. Al terminar, el proyecto aparece en "Mis proyectos" con nombre, fecha, puntuación, número de viviendas y miniatura del plano.

**CU-2 — Volver mañana.** Abre ArchMuse. La pantalla inicial es la lista de proyectos, no el formulario de subida. Pulsa "Calle Mayor" y en menos de un segundo está donde lo dejó: misma vivienda, mismo modo, mismo encuadre. No se ha llamado a la IA.

**CU-3 — Re-subida del mismo archivo.** Vuelve a arrastrar el mismo DXF (porque no recuerda que ya está). El sistema reconoce el contenido por su hash, no crea un duplicado: abre el proyecto existente y avisa de que ya estaba analizado.

**CU-4 — Versión nueva del plano.** Modifica el DXF en AutoCAD y lo sube. El contenido difiere: se analiza de verdad (y se paga la llamada de IA), y se guarda como **versión nueva del mismo proyecto** si el nombre de archivo coincide, conservando la anterior.

**CU-5 — Borrar.** Elimina un proyecto que ya no le sirve. Se pide confirmación y se borran sus datos y su DXF del disco.

**CU-6 — Proyecto generado por IA.** Un proyecto creado con `/api/generar` se guarda igual que uno analizado, pero sin DXF de origen: su entrada de origen son los parámetros del formulario.

## 6. Casos límite

- **Mismo contenido, parámetros distintos** (otro norte, otra ciudad → otra zona CTE): el hash debe cubrir contenido **y** parámetros. Si solo cubriera el archivo, se devolvería un análisis con la orientación equivocada. Es el caso límite más peligroso de este PRD.
- **Bug conocido de tipología/zona climática en `/api/analizar`** (`TECH_REVIEW.md`): hoy `tipologia` y `ciudad` llegan del formulario pero no siempre se propagan correctamente. Cachear **congela ese bug** en disco: un análisis cacheado con el bug se seguirá sirviendo aunque el bug se arregle después. Mitigación obligatoria: incluir en la clave de caché una **versión del motor de análisis**, de modo que cualquier cambio en `analyzer/` invalide lo cacheado.
- **DXF que no parsea:** no se crea proyecto. El error se sigue devolviendo como hoy (HTTP 400).
- **Análisis sin `ANTHROPIC_API_KEY`:** `analyze_with_ai` devuelve `None` sin lanzar. Ese proyecto se guarda **marcado como "sin análisis de IA"** y no debe cachearse como definitivo: al reabrirlo con la clave configurada, debe poder completarse.
- **DXF de 25 MB** (límite actual de `MAX_CONTENT_LENGTH`): guardar el original multiplica el disco. Decidir explícitamente si se conserva el DXF (necesario para re-analizar tras un cambio de motor) o solo su hash. Recomendación: conservarlo, con un aviso de espacio a partir de N proyectos.
- **Almacenamiento corrupto o de una versión anterior del esquema:** al leer un proyecto ilegible, no romper la lista — mostrarlo como "no se puede abrir" y permitir borrarlo.
- **Dos pestañas del navegador sobre el mismo proyecto:** la última en escribir gana. Aceptable para un solo usuario local; no se implementa bloqueo.
- **Miniatura:** se genera del SVG ya producido por `plan_svg.py`. Si el proyecto no tiene plano dibujable, la tarjeta va sin miniatura, no con un icono de relleno.

## 7. Flujo del usuario

1. Abre ArchMuse → **pantalla de proyectos** (lista, no formulario). Si no hay ninguno, un único punto de entrada: analizar un DXF o generar un proyecto.
2. Analiza un DXF → al terminar entra directamente al espacio de trabajo del proyecto recién creado.
3. Trabaja: cambia de vivienda, de modo, hace zoom. Cada cambio se guarda solo, sin botón "Guardar" (ver §14 sobre el menú "Guardar").
4. Cierra el navegador.
5. Vuelve a abrir → lista de proyectos → pulsa uno → aparece exactamente como lo dejó, sin recalcular ni llamar a la IA.
6. Desde el espacio de trabajo puede volver a la lista de proyectos en cualquier momento.

## 8. Criterios de aceptación

1. Analizar un DXF crea una entrada persistente en disco que sobrevive a reiniciar `python app.py`.
2. `GET /api/proyectos` devuelve, para cada proyecto: id, nombre, fecha de creación, fecha de última modificación, puntuación global, número de viviendas y miniatura.
3. `GET /api/proyectos/<id>` devuelve un payload **idéntico** al que devolvió `/api/analizar` cuando se creó (comparación byte a byte del JSON serializado).
4. Abrir un proyecto existente **no** produce ninguna llamada a `api.anthropic.com` (verificable interceptando el cliente en un test).
5. Subir dos veces el mismo DXF con los mismos parámetros produce **un solo** proyecto y **una sola** llamada a la IA.
6. Subir el mismo DXF con distinto `norte` produce **dos** análisis distintos (no se sirve el cacheado).
7. Cambiar cualquier archivo de `analyzer/` (reflejado en la versión del motor) invalida la caché: el siguiente análisis del mismo DXF se recalcula.
8. Al reabrir un proyecto se restauran vivienda seleccionada, modo activo y encuadre del plano.
9. Borrar un proyecto elimina su entrada, su payload y su DXF; la lista queda consistente.
10. Con el almacenamiento vacío o borrado a mano, la aplicación arranca sin error y muestra la lista vacía.

## 9. Riesgos

- **Compite directamente con `REFACTOR_MASTERPLAN.md`.** Este PRD introduce una capa nueva (almacenamiento) en un proyecto que aún no tiene suite de test golden-master (tarea 18 del masterplan) ni ha corregido el bug de tipología/zona climática. Añadir persistencia antes de tener tests significa que cualquier regresión futura en `analyzer/` se propaga a datos guardados y no hay red que la detecte. **Recomendación fuerte: la tarea 18 del masterplan debería ir antes que este PRD, o como primera tarea dentro de él.**
- **Caché que sirve resultados obsoletos.** Es el riesgo funcional número uno y la razón de la versión del motor en la clave. Un caché mal invalidado es peor que no tener caché: el usuario ve un diagnóstico antiguo y no tiene forma de saberlo.
- **Elección de almacenamiento.** SQLite es lo correcto para un producto que crecerá (consultas, versiones, migraciones); un directorio con JSON es más simple y depurable a mano hoy. Elegir JSON ahora tiene coste de migración después. Mi recomendación: **SQLite desde el principio** (viene en la stdlib, no añade dependencia) con el payload como blob JSON y el DXF en disco.
- **Crecimiento de disco sin control.** N proyectos × (DXF + payload + miniatura). Sin política de limpieza, esto crece indefinidamente en la máquina del usuario.
- **Datos del cliente en disco sin cifrar.** Los DXF de un estudio son material de proyecto, a veces bajo NDA. Guardarlos en `~/.archmuse/` es razonable en local, pero convierte un problema que hoy no existe (nada se guarda) en uno que sí. Documentarlo, no ignorarlo.
- **Superficie de ataque nueva:** un id de proyecto sin validar en la ruta es un path traversal. Los ids deben generarse, nunca derivarse de la entrada del usuario.

## 10. Impacto sobre módulos existentes

- **`app.py`** — cambio mayor: rutas nuevas (`/api/proyectos`, `/api/proyectos/<id>`, borrado, estado de sesión) y `/api/analizar` deja de ser sin estado. Es hoy un archivo de 310 líneas sin capa de datos; conviene extraer el almacenamiento a un módulo propio y no engordar `app.py`.
- **`analyzer/` (módulo nuevo, p. ej. `storage.py`)** — toda la persistencia aquí. **Ningún módulo de análisis existente debe importarlo**: el analizador no sabe que existe una base de datos.
- **`analyzer/plan_svg.py`** — se le pide una miniatura. Cuidado: el mismo SVG alimenta el informe HTML de la CLI y el PDF (`pdf_report.py`). La miniatura debe derivarse del SVG ya generado, sin tocar su función actual.
- **`analyzer/ai_analyst.py`** — no cambia su lógica, pero deja de llamarse en el camino cacheado. Cualquier cosa que hoy asuma "si hay análisis, hubo llamada" deja de ser cierta.
- **`static/index.html`** — pantalla nueva (lista de proyectos) antes del espacio de trabajo, y guardado automático del estado de sesión. Es el archivo de 5.700 líneas que ya concentra tres iteraciones de rediseño; este PRD añade una segunda pantalla de primer nivel. Buen momento para evaluar si sigue siendo un solo archivo.
- **`main.py` (CLI)** — no se toca. La CLI sigue siendo sin estado.

## 11. Plan de implementación dividido en pequeñas tareas

Cada tarea ≤ 2 horas, independientemente verificable.

1. **Test golden-master mínimo** de `/api/analizar` sobre un DXF de referencia: congelar el JSON actual como fixture. Sin esto, nada de lo siguiente es seguro. *(Puede ser la tarea 18 del masterplan, reducida a este endpoint.)*
2. **`analyzer/storage.py`**: esquema SQLite (`proyectos`, `versiones`) + `init_db()` idempotente en `~/.archmuse/archmuse.db`. Sin integrar todavía.
3. **Hash de análisis**: función que combina bytes del DXF + parámetros normalizados + versión del motor → clave estable. Tests de las tres dimensiones por separado.
4. **Versión del motor**: constante derivada del contenido de `analyzer/*.py`, para que un cambio de código invalide la caché automáticamente.
5. **Guardar tras analizar**: `/api/analizar` persiste proyecto + payload + DXF. La respuesta HTTP no cambia salvo por un `proyecto_id` nuevo.
6. **Camino de caché**: si el hash ya existe, devolver lo guardado sin parsear ni llamar a la IA. Verificar el criterio 5.
7. **`GET /api/proyectos`**: lista con los metadatos de §8.2.
8. **`GET /api/proyectos/<id>`**: payload completo. Validación estricta del id.
9. **Miniatura**: generar y guardar el SVG reducido al crear el proyecto.
10. **`DELETE /api/proyectos/<id>`**: borrado de las tres cosas (entrada, payload, DXF).
11. **Pantalla de proyectos en la SPA**: lista, apertura, borrado con confirmación, estado vacío.
12. **Estado de sesión (servidor)**: campo por proyecto con vivienda, modo y encuadre; `PUT` con escritura diferida.
13. **Estado de sesión (cliente)**: guardar al cambiar (con retardo), restaurar al abrir.
14. **Versiones**: subir un DXF de nombre igual y contenido distinto crea versión nueva conservando la anterior.
15. **Proyectos generados**: `/api/generar` persiste igual, con parámetros en lugar de DXF.
16. **Límite de disco**: contar el espacio ocupado y avisar a partir de un umbral.

Las tareas 1–8 forman un entregable útil por sí solo (persistencia + caché, sin interfaz nueva); 11–13 son la mitad visible.

## 12. Plan de pruebas

- **Golden master** (tarea 1): el payload de un DXF de referencia no cambia en ningún punto del desarrollo. Es la única defensa real contra que la persistencia altere el análisis.
- **Idempotencia de la caché**: analizar dos veces → un proyecto, una llamada de IA, dos payloads idénticos.
- **Invalidación**: por parámetros y por versión del motor, con test independiente para cada uno.
- **Cliente de IA interceptado**: un doble que falla si se le llama; abrir un proyecto guardado no debe llamarlo (criterio 4).
- **Reinicio**: crear proyecto, matar el proceso Flask, arrancar de nuevo, abrir el proyecto.
- **Almacenamiento hostil**: base de datos ausente, vacía, corrupta, con un registro de esquema antiguo, con el DXF borrado a mano.
- **Path traversal**: ids como `../../etc/passwd` deben rechazarse, no leerse.
- **Humo en la SPA**: extender el smoke test jsdom actual (72 comprobaciones) a la pantalla de proyectos y a la restauración de estado.

## 13. Métricas para medir el éxito

- **Llamadas a la API de Anthropic por análisis abierto.** Hoy es 1,0 por apertura. Objetivo < 0,3. Es la métrica que prueba que la caché funciona y la que se traduce en dinero.
- **Proyectos reabiertos / proyectos creados.** Si tiende a 0, el gestor de proyectos no sirve para nada y hay que revisar la premisa completa.
- **Días distintos de uso por proyecto.** Un proyecto que se abre tres días distintos es un producto con retención; uno que se abre una vez es un informe.
- **Tiempo hasta ver el diagnóstico al reabrir.** Objetivo < 1 s, frente a los segundos que hoy cuesta parsear + evaluar + esperar a la IA.
- **Contra-métrica: análisis servidos desde caché que el usuario re-analiza a mano.** Si sube, la caché está sirviendo resultados que el usuario no se cree.

## 14. Posibles motivos para NO implementar la idea

**El argumento en contra más serio es el orden.** ArchMuse tiene hoy un bug conocido y sin corregir en la propagación de tipología/zona climática (`TECH_REVIEW.md`) y no tiene suite de regresión. Construir una capa de persistencia con caché sobre un motor que aún produce resultados dudosos significa **guardar en disco resultados dudosos** y servirlos durante meses. La caché amplifica la calidad del análisis, sea buena o mala. Si hay que elegir entre este PRD y arreglar el motor + tests, se arregla el motor.

**Sobre partes concretas de lo pedido, mi recomendación difiere:**

- **"Guardar" en el menú no debería existir.** Un menú Guardar implica que hay cambios que se pueden perder. Aquí el usuario no edita nada: analiza. Todo se guarda solo. Poner "Guardar" es copiar la estética de Revit sin su modelo mental — y un botón que no hace nada observable es exactamente el tipo de elemento que el propio rediseño quiere eliminar. **Alternativa: no hay Guardar; hay "Proyecto → Volver a analizar" para forzar el recálculo.**
- **Cuentas, licencia y "cerrar sesión" son prematuros.** Esto es una aplicación Flask local de un solo usuario. Autenticar contra qué. Un sistema de cuentas añade superficie de ataque, un servidor que mantener y trabajo de por vida, para resolver un problema que aún no existe. **Alternativa: el menú "Usuario" se queda en "Ajustes", sin perfil, sin licencia, sin logout, hasta que haya despliegue multiusuario real.** Merece su propio PRD el día que lo haya, no antes.
- **El árbol "Planta 1 → Vivienda A" no es implementable hoy para un DXF analizado.** El concepto de planta solo existe para proyectos **generados**, y está codificado en el nombre de la vivienda (`"Planta 1 · …"`), leído por expresión regular en `evaluator.py:2579`. Un DXF analizado produce viviendas tipo `VT1/3` sin ninguna planta asociada — el propio docstring lo dice: no se asignan a ninguna planta. Un árbol con plantas para DXF exigiría **inferir la planta del plano**, que es un problema de análisis, no de interfaz, y es un PRD aparte. **Alternativa inmediata: árbol de dos niveles (Proyecto → Viviendas), con plantas solo cuando el dato existe de verdad.**
- **El panel de consumo de IA (tokens, coste, % restante) no se puede construir hoy.** No existe ninguna instrumentación: `ai_analyst.py` descarta el objeto `usage` de la respuesta, no hay registro de llamadas, no hay acumulador de coste, y el "% de API restante" sencillamente no es un dato que la API de Anthropic exponga. Es una capacidad nueva completa (medición → almacenamiento → visualización). **PRD aparte.** *(Aparte: `MODEL = "claude-sonnet-4-6"` en `ai_analyst.py:30` apunta a un modelo de generación anterior; conviene revisarlo con independencia de este PRD.)*

---

**Decisión:** _pendiente de revisión por Pablo_
