# PRD — Segmentación de Plantas del Sólido Capaz + integración visual con Programa de Necesidades

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 1. Problema que resuelve

El Sólido Capaz (`docs/prd/2026-08-17-solido-capaz-sandbox.md`) y el Programa de Necesidades (`docs/prd/2026-08-17-programa-de-necesidades.md`) ya calculan correctamente si un programa cabe en la edificabilidad legal — pero la comparación hoy es solo texto en el HUD ("Supera edificabilidad permitida en +X m²", "6 / 4 máx. (Sólido Capaz)"). El propio Sólido Capaz sigue siendo una única masa extruida (con líneas finas de planta añadidas en la Fase 2 del mismo encargo, puramente decorativas) — no hay ninguna forma de VER en el modelo 3D qué plantas del programa caben dentro del envolvente legal y cuáles no, ni de inspeccionar el volumen planta a planta.

Origen: petición directa de Pablo, "Fase 3" del mismo hilo de trabajo iniciado hoy (Fases 1 y 2, ya implementadas).

## 2. Usuario afectado

El mismo arquitecto/estudio que ya usa el Sandbox + Programa de Necesidades — un paso más adelante en el mismo flujo: de "sé que el programa no cabe" (hoy, en texto) a "veo exactamente qué plantas no caben" (esta pieza, en 3D). Sigue siendo la herramienta de encargo real (caso de prueba: concurso EMVS Berrocales 01), no un cambio de usuario objetivo.

## 3. Objetivo de negocio

Continúa la misma pieza de conversión a SaaS B2B ya señalada en el PRD del Programa de Necesidades (§3 de ese documento): una comparación visual clara entre "lo que pide el programa" y "lo que permite la parcela" es material de venta/demo directo para estudios que preparan concursos — más persuasivo que una cifra en un HUD lateral.

**Nota honesta (postura CTO):** exactamente la misma advertencia que ya dejó escrita el PRD anterior en su §3 sigue aplicando sin cambios: "Fase 2 SaaS B2B" sigue sin un documento de encaje propio. Esta es ya la tercera pieza suelta de esa línea (Sólido Capaz → Programa de Necesidades → esto) aprobada sin ver el conjunto. Lo repito aquí porque cada pieza nueva hace más cara la refactorización si al final se decide una arquitectura distinta para "Fase 2" como conjunto.

## 4. Objetivo técnico

1. **Segmentación real del Sólido Capaz:** al calcularlo (o recalcularlo), la masa se construye como N mallas independientes (una por planta legal, según `plantasEstimadas` ya calculado hoy) — forjado delgado + paño de fachada semitransparente por planta — en vez de una única extrusión. Debe seguir leyéndose como un solo volumen coherente en la vista normal (mismo aspecto visual que hoy, solo que compuesto de piezas).
2. **Vista "Plantas Explosionadas":** un control en la barra de herramientas del Sandbox alterna entre "Volumen Total" (piezas juntas, aspecto actual) y una vista con cada planta separada verticalmente un espacio fijo legible, para inspección — transición simple (interpolación de posición), sin física ni animación compleja.
3. **Capa de aviso de exceso del programa:** cuando el Programa de Necesidades tiene un nº de plantas definido (manual o por preset) MAYOR que las plantas legales del Sólido Capaz ya calculado, se añaden mallas "fantasma" adicionales por encima del volumen legal, en rojo de aviso (mismo tono `#f2a3a3` que ya usa el resto del HUD) — nunca sustituyendo ni redimensionando el Sólido Capaz legal, que sigue derivándose exclusivamente de `limitesUrbanisticos` (ocupación/altura/retranqueos/edificabilidad), igual que hoy.
4. **Sin regresión** en "+ Añadir volumen" (dibujo manual de volúmenes) ni "Generar plantas con IA" — ninguno de los dos flujos cambia de comportamiento; solo se verifica en vivo que la nueva geometría segmentada del Sólido Capaz no interfiere con ellos (comparten la misma `scene`).

## 5. Casos de uso

1. **Inspección normal:** el usuario calcula el Sólido Capaz sobre una parcela real → lo ve segmentado en plantas (forjados + fachadas), con el mismo aspecto general que ya conocía.
2. **Vista de despiece:** el usuario pulsa "Plantas Explosionadas" → las plantas se separan verticalmente, puede identificar cada nivel individualmente; vuelve a "Volumen Total" cuando quiere ver el conjunto.
3. **Programa que no cabe (caso Berrocales):** parcela cuyo Sólido Capaz legal permite 4 plantas; el usuario carga el preset Berrocales (6 plantas) → ve 4 plantas normales + 2 plantas fantasma en rojo apiladas encima, sin que la altura del Sólido Capaz legal cambie ni el HUD dé una cifra distinta a la de antes.
4. **Programa que sí cabe:** el usuario ajusta el nº de plantas del programa a 3 (por debajo del legal) → no aparece ninguna planta roja; solo se ven las plantas legales normales.
5. **Iteración en vivo:** el usuario edita el mix o el nº de plantas del programa con el Sólido Capaz ya calculado → la capa de aviso se actualiza sin que el usuario tenga que volver a pulsar "Calcular sólido capaz".

## 6. Casos límite

- **Sin Sólido Capaz calculado todavía:** no hay nada que segmentar ni ninguna capa de aviso que dibujar — mismo criterio ya usado en todo el Sandbox ("pendiente de calcular", nunca un 0 o un aviso inventado).
- **Programa sin nº de plantas definido** (campo vacío, `estado.plantas === null`): sin dato del programa no hay "exceso" que marcar — cero mallas fantasma, no una interpretación por defecto.
- **Retranqueo no aplicable (parcela cóncava):** la segmentación reutiliza el mismo `poligonoFinal` ya resuelto por `calcularSolidoCapaz()` (con o sin retranqueo aplicado) — no una geometría aparte que pueda desalinearse.
- **Cambio de parcela con "Plantas Explosionadas" activo:** el modo de vista vuelve a "Volumen Total" en cada `open()` nuevo — nunca se arrastra el modo de una parcela a la siguiente (mismo criterio que el resto del estado efímero del Sandbox, p. ej. `seleccionado`).
- **Programa con un nº de plantas muy alto sin Sólido Capaz recalculado tras cambiar altura/retranqueos:** la capa de aviso debe recalcularse contra el ÚLTIMO Sólido Capaz calculado, no contra `limitesUrbanisticos` en crudo — si el usuario cambia un límite y no vuelve a pulsar "Calcular sólido capaz" (comportamiento ya establecido: recálculo solo al pulsar, PRD del Sólido Capaz §6), la comparación sigue siendo contra el sólido antiguo, igual que ya ocurre hoy con el resto del HUD.
- **Recalcular el Sólido Capaz con la vista "Plantas Explosionadas" activa:** las mallas viejas se disponen (mismo patrón ya usado para `bordesGeometry`/`lineasPlantasGeometries`) y las nuevas nacen ya en el modo de vista activo, sin parpadeo a "Volumen Total" de por medio.

## 7. Flujo del usuario

1. Usuario abre el Sandbox con una parcela real y calcula el Sólido Capaz (manual o automático, Fase 1).
2. El volumen aparece segmentado en plantas (forjados + fachadas), visualmente equivalente al volumen único de antes.
3. Opcional: pulsa "Plantas Explosionadas" en la barra de herramientas → las plantas se separan verticalmente; pulsa de nuevo para volver a "Volumen Total".
4. Abre/edita el Programa de Necesidades (preset o manual). Si el nº de plantas del programa excede las plantas legales del Sólido Capaz, aparecen mallas rojas por encima del volumen, sin recalcular el Sólido Capaz legal.
5. Sigue editando el programa libremente — la capa roja se actualiza sola con cada cambio relevante (plantas objetivo).

## 8. Criterios de aceptación

- Al calcular el Sólido Capaz, la escena muestra plantas segmentadas (forjado + fachada por nivel) que en conjunto se ven como el mismo volumen de antes en la vista "Volumen Total".
- Existe un control "Plantas Explosionadas" / "Volumen Total" en la barra de herramientas del Sandbox, con el mismo lenguaje visual que los botones de cámara ya existentes (`.sandbox-toolbar-btn`); alternar entre los dos no relanza el cálculo del Sólido Capaz ni pierde su resultado numérico en el HUD.
- Cuando el Programa de Necesidades tiene más plantas que el Sólido Capaz legal ya calculado, las plantas excedentes se muestran como mallas independientes en rojo de aviso (`#f2a3a3`) por encima del volumen legal; el Sólido Capaz legal (altura, m² permitidos, cifras del HUD de Urbanismo) **no cambia de valor** en ningún caso por causa del programa.
- Editar el nº de plantas o cargar/cambiar el preset en Programa de Necesidades actualiza la capa roja sin que el usuario tenga que volver a pulsar "Calcular sólido capaz".
- "+ Añadir volumen" y "Generar plantas con IA" verificados en vivo tras el cambio, sin regresión de comportamiento.
- `node --check` limpio en los `.js` tocados; CSS balanceado; verificación en vivo sin errores de consola y sin caída perceptible de FPS al alternar "Plantas Explosionadas" o editar el programa.

## 9. Riesgos

- **Más mallas por gestionar:** pasar de 1 mesh a N (forjados + fachadas) por planta, más las eventuales mallas rojas de exceso, multiplica lo que hay que disponer correctamente en cada recálculo — mismo patrón de disposal explícito ya usado (`bordesGeometry`, `lineasPlantasGeometries`), pero con más superficie para un memory leak si se olvida algún array.
- **Rendimiento en "Plantas Explosionadas":** con parcelas de muchas plantas (edificios altos), la separación vertical puede generar una escena visualmente muy alta — mitigar con una animación simple (no física) y sin límite artificial de plantas, pero señalado como riesgo de UX a validar en vivo.
- **Riesgo de confusión visual** entre "envolvente legal" y "programa deseado" si el rojo no se lee inequívocamente como "esto no es legal, es lo que pide el programa" — mitigado por mantener el Sólido Capaz legal intacto (nunca sustituido) y usar el mismo rojo de aviso que el resto de la app, no un color nuevo.
- **Compite por tiempo con `REFACTOR_MASTERPLAN.md`** — mismo señalamiento no bloqueante que los PRDs anteriores de esta misma línea de trabajo.

## 10. Impacto sobre módulos existentes

- **`static/viewer-sandbox.js`:** reescribe la parte de `calcularSolidoCapaz()` que hoy crea una única `THREE.Mesh` — pasa a construir un grupo de mallas por planta. Añade el control de vista "Plantas Explosionadas"/"Volumen Total" (nuevo botón en `construirBarraHerramientas()` + función de reposicionamiento vertical). Añade la capa de aviso (mallas rojas), consultando el nº de plantas del Programa de Necesidades — requiere que `programa-necesidades.js` exponga ese dato de forma consultable hacia el Sandbox (hoy el flujo es unidireccional: Sandbox → `actualizarSolidoCapaz()` → Programa; hace falta el sentido contrario, o un callback en los puntos donde el Programa cambia sus plantas).
- **`static/programa-necesidades.js`:** necesita notificar al Sandbox cuándo cambia `estado.plantas` (preset, edición manual, autorrelleno desde el Sólido Capaz) para que la capa de aviso se actualice — nuevo callback o función exportada, sin cambiar su cálculo interno actual.
- **`static/style.css`:** clase para el nuevo botón de toggle (reutilizando `.sandbox-toolbar-btn`/`.active` ya existentes) y para el material/aspecto de las plantas de aviso si hace falta algún estilo de HUD asociado (p. ej. un contador "+2 plantas sobre el límite legal").
- **`static/index.html`:** posible nuevo botón en la barra de herramientas del Sandbox (o reutilización de un contenedor ya existente).
- **No toca `app.py` ni `analyzer/`** — capacidad enteramente de cliente sobre geometría ya resuelta en el navegador.

## 11. Plan de implementación dividido en pequeñas tareas

1. Refactor de `calcularSolidoCapaz()`: generar N mallas (forjado + fachada) por planta legal en vez de una extrusión única, manteniendo el mismo resultado numérico en el HUD (~2h).
2. Botón + lógica de "Plantas Explosionadas" / "Volumen Total": reposicionamiento vertical animado de las mallas por planta (~1.5h).
3. Exponer `estado.plantas` del Programa de Necesidades hacia el Sandbox (callback en los puntos donde cambia: preset, input manual, autorrelleno) (~1h).
4. Capa de mallas rojas de exceso: comparar plantas del programa vs. plantas legales del último Sólido Capaz calculado, dibujar/quitar según corresponda (~2h).
5. Conectar la capa de aviso a los eventos del paso 3, sin relanzar `calcularSolidoCapaz()` (~1h).
6. Verificación de no regresión en "+ Añadir volumen" y "Generar plantas con IA" (~30min).
7. Estilos CSS del botón toggle + cualquier indicador textual asociado (~1h).
8. Verificación en vivo completa: segmentación, toggle, caso Berrocales con exceso, caso sin exceso, cambio de parcela, consola limpia (~1.5h).

## 12. Plan de pruebas

- Verificación manual en Chrome en vivo (mismo patrón que las dos fases anteriores de este mismo encargo): parcela real, cálculo de Sólido Capaz segmentado, toggle de vista explosionada, preset Berrocales con y sin exceso de plantas, edición manual del programa, cambio de parcela.
- `node --check` sobre los `.js` tocados; balance de llaves del CSS añadido.
- Confirmar en consola que no aparecen errores durante el ciclo completo (calcular, alternar vista, editar programa, recalcular, cerrar Sandbox).
- Sin test automatizado de Python que tocar (módulo enteramente de cliente), consistente con el resto del Sandbox.

## 13. Métricas para medir el éxito

- Uso real del toggle "Plantas Explosionadas" en al menos una sesión de trabajo real (o de demo a un cliente/concurso).
- Cero discrepancias entre la cifra de edificabilidad/plantas legales mostrada en el HUD antes y después de esta pieza (confirma que el Sólido Capaz legal no se alteró).
- Cero regresiones reportadas en "+ Añadir volumen" / "Generar plantas con IA".

## 14. Posibles motivos para NO implementar la idea (o para acotarla más)

- **El encargo, tal como está escrito, admite una lectura que reabriría una decisión ya aprobada hoy mismo.** El PRD del Programa de Necesidades fija como decisión explícita (§ Decisión, punto 1): *"el dato del preset se trata como la meta deseada del usuario, no como el techo de validación"* — es decir, el programa y el Sólido Capaz legal pueden divergir A PROPÓSITO. El punto 2 de este encargo ("ajusta la escala vertical de las plantas al nº de niveles requeridos [por el programa]") podría leerse como "que el programa redimensione el Sólido Capaz legal", lo cual anularía esa decisión. Este PRD propone la lectura alternativa (Sólido Capaz legal fijo + capa de aviso superpuesta) precisamente para no chocar con ella — **pero es una interpretación mía, no una instrucción literal**, y conviene que quede confirmada explícitamente al aprobar este documento, no asumida en silencio.
- **Alternativa más barata:** el HUD ya muestra hoy, en texto, exactamente la misma información que esta pieza representaría en 3D ("Supera edificabilidad permitida en +X m²", "6 / 4 máx. (Sólido Capaz)"). Si el objetivo inmediato es solo la validación numérica (no una pieza de demo/venta), esta tarea es una mejora de comunicación visual, no una capacidad de cálculo nueva — vale la pena en la medida en que el objetivo de negocio de §3 (material de venta B2B) sea real y cercano, no especulativo.
- **Ambigüedad de "Plantas Explosionadas" sin ejemplo visual:** el encargo no especifica el espaciado, si debe ser animado o instantáneo, ni si debe incluir alguna etiqueta por planta en ese modo — se propone en §11 la opción más simple (separación fija, transición sin física) para no sobredimensionar el alcance; si Pablo tiene una referencia visual concreta en mente, mejor confirmarla antes de construir.

---

**Decisión:** Aprobado 2026-08-17 por Pablo, confirmando la lectura propuesta en §14 (primer punto): el Sólido Capaz legal nunca cambia de valor por el Programa de Necesidades; los niveles/metros que el programa pida de más se representan en rojo sobre la masa técnica, sin alterar el volumen legal base. Las 3 piezas del encargo (segmentación en forjados/fachadas, capa roja de exceso, toggle Volumen Total/Plantas Explosionadas) se aprueban tal como están descritas en §4/§7/§8.

**Estado de implementación:** IMPLEMENTADO 2026-08-17 (mismo día de aprobación). `static/viewer-sandbox.js`: `calcularSolidoCapaz()` reescrito para construir un `THREE.Group` de piezas por planta (forjado opaco + fachada de cristal, `construirPlantasLegales`/`construirPisoSolidoCapaz`) en vez de una única malla extruida; retiradas `construirLineasPlantas`/`MAT_LINEAS_PLANTAS_SOLIDO_CAPAZ` de la Fase 2 (sustituidas por geometría real). Nuevo botón "Plantas explosionadas" en la barra de herramientas (`alternarVistaExplosionada`/`aplicarModoVistaSolidoCapaz`, separación fija de 1.4 m, sin física). Capa roja de exceso (`actualizarCapaExcesoPrograma`) añadida/retirada como hija aparte del mismo grupo, sin relanzar el cálculo legal. `static/programa-necesidades.js`: nuevo canal Programa → Sandbox (`onCambioPlantasCallback`/`notificarCambioPlantas`, parámetro `onCambioPlantas` de `montar()`) para el sentido inverso al que ya existía. Verificado en vivo con la parcela real `9654202VK3795D`: segmentación visible (4 forjados+fachadas), toggle explosionado/compacto reversible, preset Berrocales (6 plantas) mostrando 4 plantas legales azules + 2 plantas rojas de exceso apiladas encima sin alterar las cifras del Sólido Capaz legal (248 m² ocupados, 991/496 m² edificabilidad, 4 plantas — idénticas antes y después del preset), capa roja también explosionable de forma continua con las legales, "+ Añadir volumen" verificado sin regresión. Cero errores de consola. `node --check` limpio en los 2 `.js` tocados; CSS sin cambios en esta pieza (balance ya verificado, 0 de profundidad de llaves).
