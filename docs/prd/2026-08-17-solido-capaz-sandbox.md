# PRD — Sólido capaz en el Lienzo libre (Sandbox 3D)

**Estado:** Aprobado e implementado · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-17)

**Decisiones finales de Pablo, distintas de las propuestas por defecto del PRD:**
- La ocupación máxima es SOLO una métrica informativa del panel -- nunca recorta la planta del sólido. El único recorte geométrico es el retranqueo (resuelve el riesgo de §9).
- "Altura máxima (m)" es un campo NUEVO e independiente de "Plantas máx." -- sin conversión silenciosa entre los dos.
- Si el offset autointersecta (parcela cóncava), se usa la parcela ORIGINAL sin offset y se avisa con el texto exacto "Retranqueo no aplicable en zonas cóncavas" -- nunca "no se dibuja nada" (la propuesta original de §6/§11 de este documento).

---

## 0. Nota de alcance (léase antes que el resto)

Dos huecos reales entre lo que pide el encargo y lo que existe hoy en `viewer-sandbox.js`:

1. **"Altura máxima permitida" no existe como campo hoy.** El panel "Límites urbanísticos" (`construirHudUrbanismo`) tiene `ocupacion_maxima_pct`, `retranqueos_m`, `edificabilidad_maxima` y **`plantas_maximas`** (número de plantas, no metros) — `evaluator.py` y `evaluate_max_floors` trabajan igual, en plantas. No hay ningún sitio en el código de donde sacar una "altura máxima en metros" hoy. Esto ya se detectó al escribir el PRD de normativa en capas (`docs/prd/2026-08-17-normativa-urbanistica-capas-fallback.md`, §10, tarea 1) como una reconciliación pendiente — este PRD la resuelve en su propio ámbito, sin esperar a aquel (ver §4).
2. **Ninguna operación de offset/erosión de polígono existe en el código.** `viewer-geometry.js`/`viewer-terreno.js` tienen construcción de formas (`shapeFromXZ`), extrusión (`extrudeFootprint`) y comprobaciones punto-en-polígono/punto-a-borde (`puntoDentroPoligono`/`distanciaAlBordePoligono`, ambas en `viewer-sandbox.js`) — pero "mover cada lado de un polígono real hacia dentro N metros y quedarme con el polígono resultante" (erosión de Minkowski / polígono interior) no existe, y no es geométricamente trivial para un polígono real de Catastro (que puede ser cóncavo, con muchos vértices, esquinas agudas). Ver riesgo detallado en §9.

## 1. Problema que resuelve

Hoy el arquitecto tiene que calcular a mano, o a ojo, cuánto volumen puede construir de verdad respetando ocupación máxima, retranqueos y altura máxima de su parcela real — el Sandbox ya muestra la parcela y los límites, pero no traduce esos límites en un volumen 3D de referencia contra el que comparar sus propios volúmenes. Petición directa de Pablo.

## 2. Usuario afectado

El arquitecto trabajando sobre una parcela real en el Lienzo libre, que ya tiene (a mano o, en el futuro, automáticos) los límites urbanísticos cargados y quiere ver de un vistazo "esto es lo máximo que puedo construir aquí" antes de posicionar sus propios volúmenes.

## 3. Objetivo de negocio

Refuerza el mismo diferencial que ya persigue el Sandbox (maqueta técnica sobre datos reales, no una caja de arena genérica) — el "sólido capaz" es una herramienta real de estudio previo de viabilidad, un paso más hacia el "cerebro arquitectónico" de `NORTH_STAR_2031.md`, construido sobre la parcela real ya integrada (Catastro) en vez de sobre una aproximación.

## 4. Objetivo técnico

Dado el polígono real de la parcela (`parcelaPoligonoLocal`, ya calculado) y los límites urbanísticos ya cargados en el panel (`limitesUrbanisticos`):
1. Calcular el polígono interior erosionando el contorno de la parcela por `retranqueos_m` en todos los lados.
2. Extruir ese polígono hasta una altura máxima en metros — **decisión de este PRD**: se añade un campo nuevo, ligero, "Altura máxima (m)" al panel de límites ya existente (junto a "Plantas máx.", no en su lugar — son datos distintos y ambos pueden hacer falta), en vez de esperar al PRD de normativa en capas o intentar derivarlo de plantas×2.8m como aproximación silenciosa. Si el arquitecto no lo rellena, el botón se deshabilita con una nota, nunca se inventa un valor.
3. Mostrar el sólido resultante como volumen semitransparente, sin sustituir nada ya visible.
4. Calcular y mostrar 3 métricas de ESE sólido (no de los volúmenes que el arquitecto haya colocado) contra los máximos permitidos.

## 5. Casos de uso

1. Parcela real con ocupación/retranqueos/altura ya rellenados → el botón está activo; al pulsarlo aparece el sólido semitransparente sobre la parcela, con las 3 métricas en el panel.
2. Falta algún dato (retranqueo, altura, o no hay parcela real) → el botón aparece desactivado, con un texto plano explicando qué falta — nunca un error al pulsar un botón que no debería estar activo.
3. El retranqueo aplicado es tan grande que no queda polígono interior con área positiva (parcela pequeña, retranqueo grande) → no se dibuja ningún sólido; el panel dice, en texto plano, que la parcela no admite construcción con esos retranqueos — nunca una geometría degenerada ni un error técnico.
4. El arquitecto cambia un límite urbanístico (ocupación, retranqueo, altura) después de haber calculado el sólido → el sólido queda desactualizado hasta que se vuelve a pulsar el botón (no recálculo automático en cada tecla — ver §6) — o se recalcula solo, a decidir en implementación (§11, tarea con Pablo).

## 6. Casos límite

- **Polígono de parcela cóncavo** (forma en L, en U — no infrecuente en parcelas reales de Catastro): un offset ingenuo (mover cada arista por su normal y reintersecar con la siguiente) puede autointersecarse o invertir el orden de los vértices en las esquinas cóncavas. Mitigación de alcance (§9/§11): implementación acotada con detección de autointersección del resultado (reutilizando el patrón ya añadido hoy mismo en `viewer-terreno.js`, `poligonoAutointersecta`) — si el resultado es inválido, se trata como el caso 3 de arriba (sin sólido, aviso en texto plano), nunca se muestra una geometría rota.
- **Retranqueo distinto tendría sentido por fachada** (frente/fondo/laterales no son iguales en muchas ordenanzas reales) — fuera de alcance: el dato de origen (`retranqueos_m`) ya es un único valor uniforme en todo el proyecto, este PRD no cambia ese modelo de datos, solo lo usa.
- **¿Recalcular automáticamente al cambiar un límite, o solo al pulsar el botón?** Recalcular en cada cambio de input sería más "vivo" pero puede sentirse intrusivo si el arquitecto está todavía ajustando valores; mantenerlo solo bajo el botón es más simple y predecible. Se deja como decisión de implementación con Pablo (§11), pero el criterio por defecto de este PRD es "solo al pulsar", coherente con que es una acción explícita ("Calcular"), no un dato reactivo como `calcularMetricasUrbanisticas`.
- **Altura máxima informada pero sin retranqueo** (o viceversa): el botón permanece desactivado — los 3 datos (ocupación, retranqueo, altura) son necesarios juntos para un sólido con sentido; ocupación máxima sin más NO limita el sólido capaz salvo que se recorte también por superficie (ver §9, riesgo de qué pasa si el polígono erosionado ya ocupa más del % de ocupación máxima permitido — a resolver en implementación, no asumido aquí).

## 7. Flujo del usuario

1. Con una parcela real cargada y los límites de ocupación/retranqueo/altura rellenados (manual o automático), aparece activo "Calcular sólido capaz" en el panel de Urbanismo.
2. Al pulsar: se calcula el polígono interior, se extruye, se añade a la escena (nunca sustituye la parcela ni ningún volumen ya colocado).
3. El panel muestra las 3 métricas del sólido calculado.
4. El arquitecto puede seguir añadiendo/editando sus propios volúmenes con normalidad; el sólido capaz es una referencia visual, no bloquea nada.
5. Al cerrar el Sandbox o cambiar de parcela, el sólido se descarta (mismo ciclo de vida que el resto de la escena, `teardown()`).

## 8. Criterios de aceptación

- [ ] Con retranqueo/altura/ocupación reales de una parcela de prueba, el polígono interior calculado a mano (o con una herramienta GIS de referencia) coincide con el que dibuja ArchMuse, para al menos 1 parcela convexa simple y 1 parcela real con forma irregular (Catastro).
- [ ] El volumen se ve semitransparente (`opacity: 0.3`, `#6B8CAE`) con aristas blancas (`#FFFFFF`, `opacity: 0.6`), superpuesto sobre la parcela sin ocultarla ni sustituirla.
- [ ] Las 3 métricas del panel (superficie ocupada + %, edificabilidad usada + máximo, plantas estimadas) se calculan correctamente contra los límites cargados, en texto plano, sin badges ni color.
- [ ] Con un retranqueo que colapsa el polígono interior, no se dibuja nada roto — aviso en texto plano.
- [ ] Botón desactivado (no oculto) con explicación clara cuando falta algún dato necesario.
- [ ] Cero regresión sobre el resto del panel de Urbanismo y del Sandbox.

## 9. Riesgos

- **El riesgo técnico central es la erosión de polígonos reales, potencialmente cóncavos, con esquinas agudas.** No es una operación de una línea: la forma robusta y general (straight skeleton / offset con librería de geometría computacional) es una pieza de infraestructura que este proyecto no tiene ni ha necesitado hasta ahora. La alternativa barata (offset ingenuo por arista + reintersección) funciona bien para la mayoría de parcelas reales (predominantemente convexas o casi-convexas) pero puede fallar en el resto — mitigado con detección de resultado inválido (§6), nunca con un resultado silenciosamente incorrecto.
- **Ambigüedad real sobre qué limita el sólido**: ¿el offset por retranqueo, la ocupación máxima (%), o ambos a la vez (el más restrictivo)? El encargo dice "aplicar el retranqueo como offset" para la planta, y separado "edificabilidad usada... de Y m² permitidos" como una MÉTRICA a mostrar, no como un segundo recorte de la planta. Se interpreta así en este PRD (ocupación máxima se muestra como métrica de referencia, no como un segundo recorte geométrico de la planta) — a confirmar con Pablo antes de implementar, porque cambia el resultado visual.
- **Compite con el resto del roadmap activo** (dos PRDs más se aprobaron/investigaron hoy mismo en esta misma sesión) — no debería implementarse en paralelo con ellos sin que Pablo priorice explícitamente el orden.

## 10. Impacto sobre módulos existentes

- `static/viewer-sandbox.js`: nueva función de erosión de polígono (o import desde `viewer-geometry.js` si se decide compartirla), nuevo botón en el panel de Urbanismo, nuevo campo "Altura máxima (m)" en `limitesUrbanisticos`/HUD, nuevas 3 métricas, nuevo material (`MAT_SOLIDO_CAPAZ`, `MAT_BORDE_SOLIDO_CAPAZ`).
- `static/viewer-geometry.js`: candidato natural para la función de erosión si se quiere compartida con otros visores en el futuro — decisión de implementación, no de este PRD.
- **NO toca** `evaluator.py`/`app.py`: cálculo enteramente en cliente, mismo criterio que `calcularMetricasUrbanisticas` ya existente.

## 11. Plan de implementación dividido en pequeñas tareas

1. Decisión con Pablo: confirmar el criterio del riesgo de §9 (¿ocupación máxima recorta la planta del sólido, o solo es una métrica de referencia?) y si el recálculo es solo-al-pulsar o reactivo (§6).
2. Añadir el campo "Altura máxima (m)" al panel de límites urbanísticos (input nuevo, junto a Plantas máx.).
3. Función de erosión de polígono por distancia uniforme, con test aislado contra 1 caso convexo simple y 1 caso cóncavo real (parcela de Catastro ya usada en esta sesión) — detección de resultado inválido (autointersección/área no positiva) reutilizando `poligonoAutointersecta` (ya existe en `viewer-terreno.js`, ver PRD de hoy sobre edificios).
4. Botón + estado activo/desactivado con explicación en texto plano.
5. Extrusión + material + inserción en escena, sin sustituir nada existente.
6. Las 3 métricas en el panel, reutilizando el patrón ya existente de `formatearFilaHud`/`calcularMetricasUrbanisticas` (texto plano, sin badges).
7. Verificación en vivo: parcela convexa simple, parcela real cóncava, caso de colapso por retranqueo excesivo, caso de datos incompletos.

## 12. Plan de pruebas

- Test aislado de la función de erosión con al menos 2 fixtures geométricos (convexo simple, cóncavo real).
- Verificación manual en el Sandbox real (mismo patrón Chrome de esta sesión) con al menos 2 parcelas reales distintas.
- `node --check` sobre los archivos modificados.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que el sólido calculado para al menos 2 parcelas reales coincide con lo que calcularía a mano/con su criterio profesional.

## 14. Posibles motivos para NO implementar la idea (o para implementarla distinto)

- **Empezar sin la Tarea 1 (decisión sobre qué recorta la planta) es el error más probable**: implementar directo desde el encargo literal, sin confirmar si la ocupación máxima también recorta el polígono, puede producir un sólido que Pablo no reconozca como correcto la primera vez que lo vea — barato de evitar preguntando antes.
- **Alternativa más simple para la primera versión**: limitar el offset a polígonos que pasen una comprobación de convexidad, y para los cóncavos mostrar el aviso de "no disponible para esta forma de parcela" en vez de intentar un offset general desde el primer commit — reduce el riesgo técnico de §9 a costa de cobertura, ampliable después si hace falta.

---

**Decisión:** Aprobado e implementado (2026-08-17) — `viewer-sandbox.js`, `viewer-terreno.js`
(`poligonoAutointersecta` exportada para reutilizarla), `style.css`.
