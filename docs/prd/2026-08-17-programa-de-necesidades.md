# PRD — Programa de Necesidades (conectado al Sólido Capaz)

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 1. Problema que resuelve

Hoy el Sandbox calcula el Sólido Capaz (volumen máximo edificable derivado de ocupación/edificabilidad/retranqueos/plantas) pero se detiene ahí: no dice nada sobre si ese volumen sirve para el encargo real — cuántas viviendas caben, de qué tipo, si el mix pedido por un concurso o un promotor encaja en los m² disponibles. Pablo pide esto como primera pieza de la "Fase 2" (transformar ArchMuse en producto SaaS B2B comercial) y da como caso de prueba un concurso público real (EMVS "Berrocales 01") con cifras de programa concretas (edificabilidad, nº de viviendas, mix de tipologías, ratio construida/útil).

Origen: petición directa de Pablo, 2026-08-17, iniciando explícitamente la Fase 2.

## 2. Usuario afectado

El arquitecto o estudio que ya usa el Sandbox para validar la parcela y el volumen — el mismo usuario de hoy, en el mismo flujo, un paso más adelante: una vez sabe "cuánto puedo construir", necesita responder "¿qué construyo y le cabe al programa que me han pedido?". En el caso de prueba, el usuario objetivo es explícitamente uno que responde a un pliego de concurso público (EMVS), no un particular.

## 3. Objetivo de negocio

Primera pieza visible de la conversión a SaaS B2B que Pablo ha anunciado para la Fase 2. Es la capacidad que separa "visor de parcela" de "herramienta de encargo real": estudios que preparan concursos o promociones necesitan cuadrar programa contra edificabilidad constantemente, y hoy lo hacen en Excel aparte, desconectado del volumen 3D. Conectar programa↔sólido capaz en la misma pantalla es valor de producto directo, no solo estético.

**Nota honesta (postura CTO):** ninguno de los documentos estratégicos raíz (`NORTH_STAR_2031.md`, `MOAT_ANALYSIS.md`, `ROADMAP_VISION_ARQUITECTONICA.md`) menciona "programa de necesidades" ni "Fase 2 SaaS B2B" como pilar ya evaluado — `ROADMAP_VISION_ARQUITECTONICA.md` es la brújula vigente aprobada por Pablo el 2026-08-16 y cubre explícitamente cuatro pilares (hiperrealismo, asesor legal/urbanístico, sostenibilidad, navegación); esto no es ninguno de los cuatro. No es motivo para no hacerlo — Pablo puede abrir una línea de producto nueva — pero si "Fase 2 SaaS B2B" va a tener más piezas después de esta, merece su propio documento de encaje (tipo `ROADMAP_VISION_ARQUITECTONICA.md`) en vez de que cada pieza se apruebe suelta sin ver el conjunto. Lo señalo aquí en vez de callarlo.

## 4. Objetivo técnico

Con la parcela cargada y el Sólido Capaz calculado, el usuario puede definir un programa de necesidades (tipología de edificio, plantas, nº de viviendas objetivo, terciario en PB, mix de tipologías) y ver en tiempo real: (a) si la superficie construida que ese programa implica cabe en la edificabilidad máxima ya calculada, con el exceso exacto en m² si no cabe; (b) cuántas viviendas caben físicamente dadas las superficies medias configuradas; (c) el ratio de eficiencia aplicado. El estado se persiste por parcela y queda expuesto en un único objeto JS para que un futuro motor de distribución por IA lo consuma sin rehacer el modelo de datos.

## 5. Casos de uso

1. **Concurso público con pliego cerrado (caso Berrocales 01):** el usuario pulsa "Cargar Preset Berrocales 01", el panel se rellena con las cifras reales del pliego, y ve inmediatamente si el Sólido Capaz de la parcela cargada admite ese programa o lo excede.
2. **Encargo propio sin pliego:** el usuario introduce a mano nº de plantas, viviendas objetivo, mix de tipologías; el panel calcula construida objetivo y compara contra edificabilidad máxima del Sólido Capaz en tiempo real, sin preset.
3. **Iteración de mix:** el usuario ajusta el % de una tipología (p. ej. sube 3D del 20% al 30%); el resto se reajusta o se marca el desajuste (>100%) hasta que confirme; los m² totales y nº de viviendas que caben se recalculan al vuelo.
4. **Retomar un proyecto guardado:** el usuario reabre una parcela ya trabajada; el Programa de Necesidades recupera el último estado guardado en `localStorage` para esa referencia catastral, igual que ya hace hoy el panel de límites urbanísticos.

## 6. Casos límite

- **Sólido Capaz aún no calculado** (faltan datos de parcela o el usuario no ha pulsado "Calcular sólido capaz"): el panel de Programa de Necesidades debe seguir siendo usable (introducir datos, aplicar preset) pero la comparación contra edificabilidad máxima debe mostrarse como "pendiente de calcular el sólido capaz", nunca como un 0% o un falso "cumple" — mismo principio que ya aplica `datosFaltantesSolidoCapaz()` hoy.
- **Mix de tipologías que no suma 100%:** bloquear visualmente el resultado como inválido (no ocultar el panel, no impedir seguir editando) hasta que sume 100% ± una tolerancia mínima por redondeo.
- **Nº de viviendas objetivo = 0 o vacío:** no dividir por cero al calcular superficies medias; mostrar el cálculo de "viviendas que caben" igualmente si hay m² y mix definidos, sin depender del objetivo.
- **Unidad de "edificabilidad máxima" desalineada:** el Sólido Capaz de hoy guarda `edificabilidad_maxima` como ratio m²/m² (`limitesUrbanisticos.edificabilidad_maxima`, ver §10) y deriva el máximo en m² como `superficie_parcela × ratio`. El preset Berrocales da un máximo ya en m² absolutos (6.250,00 m²e) directamente del pliego, sin pasar por el ratio ni por la superficie real de la parcela cargada. Si la parcela de prueba cargada no es realmente la parcela de Berrocales, estos dos números no tienen por qué coincidir — no es un bug, es que son dos fuentes distintas. Ver decisión propuesta en §10.
- **`localStorage` no disponible** (modo privado, cuota agotada): igual que ya hace el bloque de límites urbanísticos hoy — nunca lanza, se queda con los valores por defecto/en memoria.
- **Cambio de parcela con panel ya relleno:** al cargar otra referencia catastral, el programa debe recargarse desde el `localStorage` de la nueva parcela (o quedar vacío si no hay nada guardado), nunca arrastrar los datos de la parcela anterior.

## 7. Flujo del usuario

1. Usuario abre el Sandbox con una parcela cargada (con o sin Sólido Capaz ya calculado).
2. Despliega el panel colapsable "Programa de Necesidades" en la barra lateral.
3. Opcional: pulsa "Cargar Preset Berrocales 01" → todos los campos se rellenan con las cifras del pliego.
4. Edita cualquier campo (tipología de edificio, plantas, viviendas objetivo, terciario en PB, % por tipología) — cada cambio recalcula en el momento: construida objetivo, comparación contra edificabilidad máxima del Sólido Capaz, ratio de eficiencia aplicado, nº de viviendas que caben físicamente.
5. Si la construida objetivo supera la edificabilidad máxima disponible, aparece el indicador de alerta con el exceso exacto en m².
6. El estado queda guardado automáticamente (por referencia catastral) sin acción explícita de "guardar".

## 8. Criterios de aceptación

- El panel "Programa de Necesidades" aparece colapsable en la barra lateral del Sandbox, con la estética oscura/glass ya usada por los demás paneles HUD del visor (mismas clases/convenciones que `sandbox-hud-*`, no un estilo nuevo aparte).
- Todos los campos listados en el encargo existen y son editables: tipología de edificio (select), nº de plantas, nº de viviendas objetivo, superficie terciario/PB, y distribución por tipologías (1D/2D/3D/4D) con validación de suma = 100%.
- El botón "Cargar Preset Berrocales 01" rellena exactamente los valores dados por Pablo en el encargo.
- La superficie construida total objetivo se recalcula en cada cambio de campo y se compara contra la edificabilidad máxima disponible según lo decidido en §10; si se supera, se muestra el aviso "Supera edificabilidad permitida en +X m²" en rojo de acento (mismo tono que ya usan los avisos de exceso del Sólido Capaz, no un rojo nuevo).
- El nº de viviendas que caben físicamente se recalcula a partir de las superficies medias configuradas por tipología y la construida disponible.
- El ratio construida/útil es editable, con 1.40–1.45 como rango/valor por defecto (a confirmar exactamente cuál en revisión, ver §14).
- El estado completo se guarda en `localStorage` bajo una clave ligada a la referencia catastral activa, siguiendo el mismo patrón que el bloque de límites urbanísticos existente, y se recupera al reabrir la misma parcela.
- El estado del Programa de Necesidades queda expuesto en un objeto JS accesible (mismo patrón que el resto del estado del Sandbox), documentado con su forma exacta, listo para que un consumidor futuro (motor de distribución IA) lo lea sin acoplarse al DOM.
- No se añade ningún botón o control fuera de lo descrito en el encargo (mismo criterio de alcance que ya se aplicó en la tarea anterior).
- `node --check` limpio en los archivos JS tocados; CSS balanceado; verificación en vivo en el navegador con el preset Berrocales y con datos manuales, confirmando recálculo fluido del canvas Three.js sin bloqueos perceptibles.

## 9. Riesgos

- **Coexistencia con `REFACTOR_MASTERPLAN.md`:** esta tarea no toca ningún archivo de `analyzer/` de los que el masterplan prioriza refactorizar, así que no compite directamente por el mismo código — pero sí compite por el mismo tiempo de Pablo/ingeniería. Señalado, no bloqueante.
- **Doble fuente de verdad para "edificabilidad máxima"** (ratio del Sólido Capaz vs. m² absolutos del pliego) — riesgo de mostrar una comparación que parezca autorizada pero compare cosas distintas si la parcela cargada no es realmente la del pliego. Ver §10 para la mitigación propuesta.
- **Alcance de "Fase 2 SaaS B2B" no está documentado como conjunto** (ver nota honesta en §3) — riesgo de construir piezas sueltas de un producto comercial sin haber decidido, por ejemplo, autenticación/multi-tenant, que `ROADMAP_VISION_ARQUITECTONICA.md` §5 ya identifica como prerequisito de cualquier fase de 12 meses de `NORTH_STAR_2031.md`. Este PRD no depende de eso (es una herramienta de cálculo, no cambia el modelo de datos de usuarios), pero si la Fase 2 sigue creciiendo, esa base tendrá que llegar en algún momento.
- **Ninguna prueba automatizada existente cubre HUD/paneles del Sandbox** (son JS de cliente, verificados hoy solo con Chrome en vivo) — este módulo se suma a esa misma falta de cobertura automatizada; el plan de pruebas (§12) lo asume y compensa con verificación manual en vivo, igual que las tareas anteriores de Sandbox.

## 10. Impacto sobre módulos existentes

- **`static/viewer-sandbox.js`:** consumidor directo del Sólido Capaz ya calculado (`limitesUrbanisticos.edificabilidad_maxima`, `parcelaSuperficieM2`, y el resultado de `calcularSolidoCapaz()` — hoy expuesto solo dentro de closures locales, no en un objeto de estado exportable). Para que el Programa de Necesidades pueda leer "edificabilidad máxima disponible" sin duplicar el cálculo, hace falta exponer ese dato (probablemente una variable de módulo tipo `ultimoResultadoSolidoCapaz` actualizada dentro de `calcularSolidoCapaz()`) de forma consultable por el nuevo módulo — cambio pequeño y no invasivo, pero es un cambio real sobre código que ya funciona (Sólido Capaz), así que debe hacerse con la misma disciplina de no regresión que las tareas anteriores.
- **Nuevo archivo propuesto `static/programa-necesidades.js`**, importado desde `viewer-sandbox.js`, en vez de seguir engordando `viewer-sandbox.js` (que ya es el archivo más grande del visor) — mantiene el patrón modular ya usado (`viewer-terreno.js`, `viewer-materials.js`, etc. como módulos separados que `viewer-sandbox.js` importa).
- **`static/style.css`:** nuevas clases para el panel colapsable y sus inputs — reutilizando las variables de diseño (`--text-xs`, paleta oscura/glass) ya definidas para `.sandbox-hud-*`, no un sistema de estilos aparte.
- **`static/index.html`:** nuevo `<script>`/cache-bust para el módulo nuevo, y el punto de montaje del panel dentro de la barra lateral existente.
- **Resolución propuesta para la doble fuente de "edificabilidad máxima" (casos límite, §6):** usar siempre la edificabilidad máxima **derivada del Sólido Capaz de la parcela realmente cargada** (`parcelaSuperficieM2 × limitesUrbanisticos.edificabilidad_maxima`) como el número contra el que se valida, no el valor del preset. El preset Berrocales rellena los campos de *programa* (plantas, viviendas, mix) tal cual pide Pablo, pero su cifra de "6.250 m²e" queda como referencia informativa del pliego, no como el techo activo de validación — así el indicador de alerta siempre compara contra la parcela real que el usuario tiene delante, nunca contra un dato de otro sitio. Lo marco como propuesta, no como decisión ya tomada, porque cambia ligeramente la lectura literal del encargo — confirmar en la revisión de este PRD.
- **No toca `app.py` ni `analyzer/`:** es una capacidad enteramente de cliente sobre datos ya calculados en el navegador; no requiere nuevo endpoint.

## 11. Plan de implementación dividido en pequeñas tareas

1. Exponer el resultado del Sólido Capaz (superficie construida disponible, edificabilidad máxima en m²) como estado consultable dentro de `viewer-sandbox.js`, sin cambiar su comportamiento actual (~1h).
2. Crear `static/programa-necesidades.js`: estado inicial, forma del objeto JSON, funciones puras de cálculo (construida objetivo, viviendas que caben, ratio de eficiencia) sin DOM todavía (~2h).
3. Construir el HTML/template del panel colapsable (campos + tabla de tipologías) siguiendo la convención `sandbox-hud-*` (~2h).
4. Conectar inputs → estado → recálculo en vivo, con la validación de suma 100% del mix (~2h).
5. Implementar el indicador de alerta de exceso de edificabilidad, leyendo el dato expuesto en la tarea 1 (~1h).
6. Botón "Cargar Preset Berrocales 01" con los valores exactos del encargo (~30min).
7. Persistencia en `localStorage` por referencia catastral (guardar y restaurar), siguiendo el patrón ya usado por límites urbanísticos (~1h).
8. Estilos CSS del panel (~1-1.5h).
9. Verificación en vivo: preset Berrocales, entrada manual, cambio de parcela, `localStorage` deshabilitado, comprobación de FPS/fluidez del canvas (~1h).

## 12. Plan de pruebas

- Verificación manual en Chrome en vivo (mismo patrón que las tareas anteriores del Sandbox): preset Berrocales sobre una parcela real cargada, edición manual de cada campo, mix que no suma 100%, cambio de parcela con panel relleno, `localStorage` bloqueado.
- `node --check` sobre todos los `.js` tocados/nuevos; balance de llaves en el CSS añadido.
- Confirmar contra consola que no aparecen errores JS durante el recálculo en vivo, y que no hay caída perceptible de FPS del canvas Three.js al escribir en los inputs (comprobación visual, no hay medidor de FPS automatizado hoy en el proyecto).
- No hay test automatizado de Python que tocar (módulo enteramente de cliente) — no se añade suite nueva a `tests/` para esto, consistente con que el resto de HUD del Sandbox tampoco tiene cobertura automatizada hoy.

## 13. Métricas para medir el éxito

- Uso real: si Pablo (u otro usuario del estudio) sustituye su hoja de cálculo externa para cuadrar programa vs. edificabilidad por este panel en al menos un encargo real después de entregarlo.
- Ausencia de discrepancias reportadas entre lo que el panel muestra como "edificabilidad disponible" y lo que el Sólido Capaz ya mostraba antes de esta tarea (validación de que §10 no rompe la fuente de verdad existente).
- Cero regresiones en el Sólido Capaz ya en producción tras exponer su resultado como estado consultable (tarea 1 de §11).

## 14. Posibles motivos para NO implementar la idea (o para acotarla más)

- **El encargo mezcla una decisión de producto ya cerrada (implementar el panel) con varios parámetros aún ambiguos** que conviene fijar antes de escribir código, no durante: (a) el ratio construida/útil, ¿es un input editable con 1.40–1.45 como valor por defecto, o un rango fijo no editable?; (b) cuando el mix por tipología determina "viviendas que caben", ¿se usa el punto medio de cada rango de superficie (p. ej. 2D = 55 m²u) o hace falta un input de superficie media editable por tipología?; (c) "Nº de Plantas" del programa, ¿debe coincidir con las plantas ya usadas por el Sólido Capaz o es independiente (y si difiere, cuál manda)? Ninguna de estas tres rompe el PRD, pero decidirlas ahora evita retrabajo.
- **Como se señala en §3, esto abre una línea de producto (Fase 2 SaaS B2B) sin un documento de encaje propio** — si la intención es que vengan más piezas de Fase 2 después de esta, un documento corto de alcance (qué es Fase 2, qué NO es, cómo se relaciona con `NORTH_STAR_2031.md`) evitaría aprobar piezas sueltas sin ver el conjunto, tal como ya se hizo para el visor 3D/entorno con `ROADMAP_VISION_ARQUITECTONICA.md` el 2026-08-16. No es motivo para bloquear esta tarea concreta, sí para no asumir que "Fase 2" ya está tan definida como "programa de necesidades — Berrocales 01".
- **Alternativa más barata a considerar:** si el objetivo inmediato es solo validar el caso Berrocales una vez (no un panel reutilizable en producción), un cálculo puntual fuera de la UI habría sido más rápido — pero el encargo pide explícitamente un panel persistente conectado al estado del Sandbox, así que esta alternativa no encaja con lo pedido; se menciona solo por completitud del análisis honesto que exige esta sección.

---

**Decisión:** Aprobado 2026-08-17 por Pablo, con las siguientes resoluciones explícitas a §10/§14:

1. La validación contra el Sólido Capaz usa SIEMPRE la edificabilidad de la parcela real cargada (confirma la propuesta de §10). El dato del preset (p. ej. 6.250 m²e) se trata como la **meta deseada del usuario**, no como el techo de validación.
2. Ratio Construida/Útil: editable, valor por defecto 1.42 (1.45 al cargar el preset Berrocales).
3. "Viviendas que caben": se calcula con los puntos medios de cada tipología (1D: 45 m², 2D: 55 m², 3D: 70 m²), con edición secundaria de esas superficies medias.
4. Sincronización de plantas: el nº de plantas del Programa de Necesidades se vincula al del Sólido Capaz, respetando la altura máxima permitida por la normativa de la parcela — no es un campo independiente.

**Estado de implementación:** IMPLEMENTADO 2026-08-17 (mismo día de aprobación). Nuevo módulo `static/programa-necesidades.js` (cliente puro, importado por namespace desde `static/viewer-sandbox.js`), panel `.sandbox-hud-programa` en `static/style.css`, cache-bust en `static/index.html`. Decisión 4 implementada como autorrelleno-mientras-no-se-toque + aviso de exceso (nunca recorte silencioso), consistente con el resto del Sandbox. Verificado en vivo con la parcela real `0150501VK4705A`: preset Berrocales, cálculo de Sólido Capaz, alerta de exceso de edificabilidad, aviso de exceso de plantas, validación de mix ≠ 100%, persistencia por referencia catastral tras cerrar/reabrir, y aislamiento correcto entre referencias catastrales distintas. Cero errores de consola. `node --check` limpio en los 2 `.js` tocados; CSS balanceado (744/744 llaves).
