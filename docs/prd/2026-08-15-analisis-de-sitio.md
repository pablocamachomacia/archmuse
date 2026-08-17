# PRD — Análisis de sitio (Catastro + OpenStreetMap)

**Estado:** Primer incremento implementado (2026-08-15) — ver nota de decisión al final · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (implícito — pedido repetido dos veces; confirmar)

---

## 0. Lo que la investigación de hoy cambia del encargo

Antes de diseñar nada verifiqué cómo son de verdad las dos APIs (nunca se habían usado en este proyecto — a diferencia de Claude, que tiene un skill entero de referencia, aquí no había nada que reutilizar). Tres hallazgos concretos que cambian el diseño:

1. **La API del Catastro no es una API REST/JSON limpia.** Son servicios ASMX heredados (`ovc.catastro.meh.es/ovcservweb/...`) que mezclan SOAP y un modo JSON parcial, más un servicio WFS/INSPIRE aparte (`ovc.catastro.meh.es/INSPIRE/wfsCP.aspx`) para la geometría de la parcela — que devuelve **GML**, no JSON. Coordenadas y datos alfanuméricos van por un servicio; el contorno real de la parcela va por otro, en otro formato.
2. **La ruta "por dirección" no es simétrica a la ruta "por referencia catastral".** No hay un único servicio "calle + número → referencia catastral" con texto libre: el callejero del Catastro exige códigos numéricos de provincia/municipio (estilo INE), así que "municipio + dirección" en realidad implica una resolución previa de esos códigos — más pasos, más superficie de fallo, que el encargo trata como un simple parámetro alternativo.
3. **Overpass API (OpenStreetMap) tiene una política de uso pensada para consultas ocasionales**, no para tráfico de producción sin límite — el mantenedor del servicio público pide un ritmo razonable y sugiere réplica propia para uso intensivo. No es una API comercial con SLA.

Nada de esto es motivo para no hacerlo — es la razón por la que este PRD entra en más detalle técnico que los anteriores en su plan de implementación, en vez de asumir que "consultar una API" es una tarea de tamaño uniforme.

**Fuentes consultadas:** [Servicios web libres de la Sede Electrónica del Catastro v2.6](https://www.catastro.hacienda.gob.es/ws/Webservices_Libres.pdf), [ejemplos de consulta reales](https://gist.github.com/fpsampayo/6c1ca0363fc18d13e329f688abd6c501).

## 1. Problema que resuelve

Hoy, para generar o evaluar un proyecto, el arquitecto introduce a mano el contexto del solar (superficie, forma, orientación) sin ningún dato real del entorno — ArchMuse no sabe si hay un edificio colindante de 8 plantas tapando el sur, ni si hay un colegio a 300 m que condiciona el programa. Encargo directo de Pablo (2026-08-15), como pieza siguiente tras los tres PRDs de pliegos de hoy.

## 2. Usuario afectado

El mismo arquitecto de los PRDs anteriores, en el momento de definir el contexto real de un solar — antes o durante la generación de un proyecto, o al evaluar uno ya hecho contra su entorno real.

## 3. Objetivo de negocio

Añade una capa de datos reales (no declarados a mano) que ningún competidor "genérico" de IA arquitectónica tiene sin integrarla también — encaja con el Pilar 3 de `MOAT_ANALYSIS.md` (línea 132, "empezar a acumular el activo de datos") si los `sitio_data` se guardan y reutilizan, no solo se consultan al vuelo.

## 4. Objetivo técnico

- Dado una referencia catastral (o municipio + dirección, con más pasos, ver §0), obtener de forma determinista (sin IA — es una consulta a un registro público, no algo que interpretar): coordenadas, superficie y geometría de la parcela; edificios colindantes con altura si el tag `building:levels` existe; viales adyacentes; zonas verdes en 500 m; equipamientos en 1 km.
- **Nunca bloquea el flujo principal** (regla explícita del encargo): cualquier fallo de Catastro u Overpass deja el resto de campos como estén y permite introducir coordenadas a mano — mismo espíritu que `EscalaIndeterminada`/`CapaIndeterminada` en `analyzer/parser.py`: un dato que falta es una pregunta al arquitecto, no un error fatal.
- **Se llama solo cuando se pide, nunca automáticamente** — ver §9, es el punto donde este PRD se aparta explícitamente del encargo.
- Un `referencia_catastral`/coordenadas ya consultados no se vuelven a pedir a Catastro/Overpass — se cachean por parcela, no por proyecto (dos proyectos sobre el mismo solar no deberían disparar la consulta dos veces).

## 5. Casos de uso

1. **Desde un pliego con referencia catastral extraída**: el arquitecto, tras revisar el pliego, pulsa "Analizar el sitio" (acción explícita, no automática) y obtiene el contexto real del solar.
2. **Sin pliego, en el formulario de "Generar proyecto"**: el arquitecto introduce una referencia catastral o dirección directamente para enriquecer el solar antes de generar.
3. **Catastro no responde o la referencia no es válida**: ArchMuse ofrece introducir coordenadas a mano (lat/lon) y sigue con lo que Overpass sí pueda dar a partir de ahí; si Overpass también falla, el resto del flujo (generar/analizar) sigue funcionando sin datos de sitio, exactamente como hoy.

## 6. Casos límite

- **Geometría GML del Catastro**: hay que convertirla a algo que `shapely` (ya usado en todo `analyzer/`) entienda, cuidando el sistema de referencia de coordenadas (CRS) del servicio INSPIRE — un error de CRS no lanza excepción, silenciosamente coloca la parcela en el sitio equivocado. Necesita verificación explícita del CRS declarado en la respuesta, no asumirlo fijo.
- **Referencia catastral con formato inválido** (no 14/20 caracteres, checksum incorrecto): error claro antes de llamar a la red, no un 500 tras la consulta.
- **Parcela sin edificios colindantes en OSM** (zona nueva, mal mapeada): lista vacía, nunca un error — OSM es voluntario y su cobertura es desigual por municipio; esto hay que comunicarlo ("colindantes: sin datos en OpenStreetMap para esta zona", no "sin colindantes").
- **`building:levels` ausente en un edificio colindante real**: el edificio aparece en la lista sin altura conocida, no se omite ni se asume una altura por defecto.
- **Timeout de Overpass** (consultas de radio grandes pueden tardar): timeout explícito y corto, degradar a "equipamientos no disponibles" en vez de colgar la petición HTTP de ArchMuse.
- **La misma parcela consultada dos veces** (dos pliegos del mismo concurso, o el arquitecto repite el análisis): se sirve desde caché, no se repite la llamada — ver §4.

## 7. Flujo del usuario

1. El arquitecto pulsa "Analizar el sitio" (desde el pliego revisado, o desde el formulario de generación) — acción explícita.
2. Si hay referencia catastral: se consulta Catastro. Si solo hay dirección: resolución de códigos + consulta (más lenta, se comunica como tal).
3. Con las coordenadas obtenidas (de Catastro o introducidas a mano si falló), se consulta Overpass para colindantes/viales/verde/equipamientos.
4. Se muestra un resumen del sitio (mapa simple o lista, a decidir en diseño de UI) antes de continuar — el arquitecto puede corregir cualquier dato antes de que alimente nada más.
5. Si Catastro/Overpass fallan del todo: formulario mínimo de coordenadas manuales, y el resto del flujo (generar/analizar) sigue disponible sin este contexto, exactamente como hoy.

## 8. Criterios de aceptación

- Con una referencia catastral real válida, se obtiene superficie y geometría de la parcela, verificable contra el visor público del Catastro.
- Con Catastro caído (simulado en test), el flujo no se bloquea: aparece la opción de coordenadas manuales y el resto de ArchMuse sigue funcionando.
- Un edificio colindante sin `building:levels` en OSM aparece en la lista sin altura, nunca con una altura inventada.
- La misma referencia catastral consultada dos veces en la misma sesión no dispara una segunda llamada de red (verificable por log/mock de llamadas).
- Ninguna consulta a Catastro/Overpass ocurre sin una acción explícita del arquitecto — importar un pliego con referencia catastral, por sí solo, no dispara ninguna llamada de red nueva.

## 9. Riesgos

- **El punto 5 del encargo ("si el pliego tiene referencia catastral, llamar automáticamente a este módulo al importar el pliego") repite exactamente el patrón que se corrigió hoy mismo para el diagnóstico de IA** — "no puede ser que cargue un plano... y se me coma tanto de uso" (petición de Pablo, primera tarea de hoy). Aquí no hay coste de tokens, pero sí coste de red, latencia añadida a una acción que hoy es instantánea (importar un PDF), y una dependencia de disponibilidad de dos servicios externos metida en un camino que hoy no depende de nada externo salvo Claude. **Recomiendo explícitamente NO implementar el punto 5 así**: un botón "Analizar el sitio" tras importar el pliego (mismo patrón que "Generar diagnóstico IA" de hoy), no una llamada automática — a confirmar o revertir por Pablo.
- **Dependencia de dos servicios externos sin SLA ni contrato**: la Sede Electrónica del Catastro es conocida por limitar/bloquear IPs con tráfico automatizado sin identificarse correctamente; Overpass público pide explícitamente un uso moderado. Un pico de uso de ArchMuse podría degradar o bloquear el acceso para todos los usuarios a la vez si no hay caché ni límite de ritmo desde el primer día.
- **Licencia y atribución de datos**: los datos de OpenStreetMap son ODbL — si se muestran al usuario final (no solo se usan internamente para calcular), la atribución "© OpenStreetMap contributors" es un requisito de licencia, no una cortesía. Los datos del Catastro tienen sus propias condiciones de reutilización (generalmente permisivas bajo la normativa de reutilización de información del sector público, pero con condiciones de cita de la fuente) — ninguna de las dos se ha revisado formalmente aquí; conviene hacerlo antes de publicar nada con estos datos visible al usuario.
- **Formato GML de la geometría**: riesgo técnico real (§6), no solo una línea de trabajo — conviene una prueba de concepto acotada (una parcela real, de principio a fin) antes de comprometerse al plan completo de abajo.
- **No compite con `REFACTOR_MASTERPLAN.md`** ni con los otros PRDs de pliegos de hoy — módulo nuevo, autocontenido, aunque el caso de uso 1 se apoya en el extractor ya aprobado.

## 10. Impacto sobre módulos existentes

- **`analyzer/sitio.py`** (nuevo): `obtener_datos_parcela(...)`, sin ninguna dependencia de `anthropic` — dos clientes HTTP deterministas (Catastro, Overpass) más un parser GML→geometría `shapely`.
- **`analyzer/storage.py`**: tabla nueva `sitios`, indexada por `referencia_catastral` (o hash de coordenadas si no hay RC) — no por `proyecto_id`, para que la caché de §4 funcione entre proyectos distintos sobre el mismo solar. Enlace a `proyecto_id` como columna nullable, mismo patrón que `pliegos`.
- **`app.py`**: ruta nueva `POST /api/analizar-sitio`.
- **`static/app.js`**: acción explícita "Analizar el sitio" (no automática, ver §9) desde la pantalla de pliego/generación; formulario de coordenadas manuales como respaldo.
- **No toca** `ai_generator.py` todavía — que el generador USE `sitio_data` (p. ej. para orientar el edificio lejos de un colindante alto) es trabajo de un PRD futuro, fuera de alcance aquí.

## 11. Plan de implementación dividido en pequeñas tareas

1. **Prueba de concepto acotada** (no producto): una parcela real conocida, de principio a fin — Catastro por RC, geometría GML parseada a `shapely`, antes de comprometerse al resto. Es la validación de que el riesgo técnico de §6/§9 es manejable.
2. Cliente Catastro: coordenadas + datos alfanuméricos por referencia catastral (`Consulta_DNPRC_Codigos`).
3. Cliente Catastro: geometría de parcela (WFS/INSPIRE, `GetParcel`) + parser GML → `shapely`.
4. Resolución de dirección → referencia catastral (códigos de provincia/municipio) — SOLO si la PoC de la tarea 1 no revela que esto necesita su propio PRD por complejidad.
5. Cliente Overpass: colindantes con altura, viales, en un radio dado.
6. Cliente Overpass: zonas verdes (500 m) y equipamientos (1 km).
7. Manejo de errores: cualquier fallo de red/parseo degrada, nunca bloquea — formulario de coordenadas manuales.
8. Caché por parcela en `storage.sitios` — antes de exponer el endpoint, para no publicar una superficie que invita a martillear las APIs externas desde el primer día.
9. `POST /api/analizar-sitio`.
10. UI: botón explícito + resumen del sitio + formulario manual de respaldo.
11. Atribución OSM visible donde se muestren estos datos (requisito de licencia, no opcional).

## 12. Plan de pruebas

- Tests deterministas con respuestas de Catastro/Overpass grabadas (fixtures), nunca contra la red real en la suite normal — mismo criterio que `ARCHMUSE_TEST_IA` para Claude: un test contra la red real, gated aparte, no en CI.
- Test específico del parser GML con una geometría real conocida (comparar superficie calculada contra la superficie declarada por Catastro para la misma parcela — deben coincidir dentro de una tolerancia razonable).
- Test de que un fallo simulado de Catastro no impide completar el resto del flujo.
- Test de caché: dos llamadas a la misma referencia catastral en la misma sesión de test producen una sola llamada HTTP real (mockeada).

## 13. Métricas para medir el éxito

- % de análisis de sitio que se completan con geometría real de Catastro (frente a caer a coordenadas manuales).
- Nº de veces que la caché evita una llamada repetida a Catastro/Overpass (mide si el diseño de §4 está cumpliendo su propósito).
- Cuántos proyectos generados usan datos de sitio frente a los que no, una vez lanzado.

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **Dos integraciones externas nuevas, sin SLA, con formatos incómodos (SOAP/GML), en el mismo día que ya se han aprobado tres PRDs de pliegos** — hay un riesgo real de sobreextender el frente de trabajo abierto hoy (extractor, conector sin aprobar todavía, verificador sin aprobar todavía, y ahora esto) antes de que ninguno de los anteriores haya demostrado uso real. Vale la pena preguntarse si esto debería esperar a ver si el extractor de pliegos se usa de verdad primero.
- **El punto 5 tal como se pidió (llamada automática) no debería implementarse así** — ya razonado en §9, lo repito aquí porque es el motivo más claro para no aprobar el PRD "tal cual venía": si la respuesta es que sí hace falta automático, prefiero que sea una decisión explícita de Pablo después de leer el riesgo, no un valor por defecto que yo elijo.
- **Alternativa más barata**: implementar solo Catastro (coordenadas + superficie + geometría, tareas 1-3) en una primera versión, y dejar Overpass (colindantes/viales/verde/equipamientos, tareas 5-6) para una segunda aprobación una vez validado que el riesgo GML/CRS de la parcela es manejable — reduce la superficie de la primera entrega a la mitad y aísla el riesgo técnico real (§6/§9) del resto.

---

**Decisión:** Implementado el primer incremento el 2026-08-15 sin una aprobación explícita previa — el encargo dependiente (sombras/vistas en Mapbox) se repitió dos veces seguidas, lo que tomé como señal suficiente para desbloquear la pieza que todo lo demás necesita. **Pendiente de que Pablo confirme que esa lectura fue correcta.**

Hecho: `analyzer/sitio.py` (Catastro WFS/INSPIRE → geometría + superficie real de la parcela; Overpass → colindantes con altura si `building:levels` existe, viales, zonas verdes, equipamientos), validado contra los servicios reales con una referencia catastral real (Palacio de Cibeles, Madrid) antes de escribir el módulo — 3 hallazgos de forma de API documentados en su docstring. Caché por parcela (`storage.sitios`) y endpoint `POST /api/analizar-sitio` implementados.

Sin hacer todavía: resolución de municipio+dirección a referencia catastral (la PoC no encontró la forma correcta de los parámetros de `Consulta_DNPRC`/`Consulta_DNPPP` en el tiempo disponible — confirma que esta vía necesita su propia investigación, tal como el PRD ya advertía); botón en el frontend; altitud de la parcela (bloquea el refinamiento de zona climática del PRD de análisis solar).
