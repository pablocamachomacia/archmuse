# PRD — Núcleo de comunicación vertical y validación de fachada en el generador de plantas

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: que el "plano 2D" reserve automáticamente un núcleo de comunicación vertical (ascensor + escalera) y un pasillo distribuidor proporcional al número de viviendas por planta, reste esa superficie del útil distribuible, y valide fachada exterior en salón/dormitorios.

Revisado antes de escribir esto: el generador real no vive en `programa-necesidades.js` (que es solo el formulario/estimador del Sandbox, no genera geometría) sino en `analyzer/ai_generator.py`. Ese módulo ya reparte cada vivienda con un pasillo INTERNO (mínimo 1.0 m, `_PASILLO_NAME`, `place_rooms()`) y ya intenta poner el Dormitorio 1 y el salón/cocina en fachada (`ai_generator.py:78-89`) — pero todo eso es **por vivienda, aislada**. Lo que no existe en ningún sitio del código es un núcleo de comunicación **compartido entre viviendas de la misma planta** (ascensor + escalera + distribuidor común): hoy cada vivienda se genera por separado y se coloca al lado de la siguiente (`_stretch_row`, `offset_x`) sin ningún espacio común que las conecte entre sí ni con las plantas superiores. Un edificio de más de una vivienda por planta, tal como se genera hoy, no tiene forma física de subir de planta ni de darle a cada puerta un acceso desde zona común.

Esto no es un ajuste sobre el generador existente — es una pieza nueva (dimensionado de núcleo a nivel de PLANTA COMPLETA, no de vivienda) que además toca el corazón del generador (`ai_generator.py`, un módulo que el propio código señala repetidamente como "fuera de alcance" en otras tareas — señal de que es sensible). De ahí este PRD.

## 1. Problema que resuelve

Cualquier edificio generado con IA con más de una vivienda por planta es, en sentido estricto, incompleto: no tiene núcleo de comunicación vertical ni distribuidor común, así que no es construible ni cumple accesibilidad/evacuación (CTE DB-SUA/DB-SI) tal como está. Esto no es un detalle estético — socava la credibilidad del generador precisamente en su caso de uso más común (edificio plurifamiliar), que es lo que ya vimos generado en esta sesión (3 viviendas en fila, sin núcleo entre ellas).

## 2. Usuario afectado

El arquitecto que usa "Generar proyecto con IA" para un edificio con más de una vivienda por planta (tipología "Manzana cerrada" u otra plurifamiliar en el Programa de Necesidades del Sandbox).

## 3. Objetivo de negocio

Sin esto, el generador produce resultados que ningún arquitecto podría presentar como proyecto real más allá de un boceto de superficies — es una limitación que afecta directamente a si ArchMuse sirve para algo más que un reparto de m² sobre el papel. Cierra una brecha real entre "genera una distribución" y "genera un edificio habitable".

## 4. Objetivo técnico

Tres comportamientos observables, nunca dejados al criterio libre del LLM:

1. Toda planta con ≥2 viviendas reserva, de forma determinista (calculada en código, no en el prompt), un núcleo de comunicación (ascensor + escalera) y un pasillo distribuidor dimensionado según el número de viviendas de esa planta.
2. Esa superficie se resta del total útil distribuible **antes** de repartir m² entre las viviendas — no como ajuste posterior ni redondeo.
3. Toda estancia de tipo salón o dormitorio, en cada vivienda generada, tiene al menos un lienzo de fachada exterior real (perímetro del edificio, nunca un patio interior ciego ni una medianera). Si no puede garantizarse, se marca como advertencia — mismo patrón que `advertencias` en `GeneratedProject` (`ai_generator.py`) — nunca se oculta el incumplimiento ni se fuerza una solución inventada.

## 5. Casos de uso

1. Edificio plurifamiliar de 3 viviendas/planta: se genera un núcleo+pasillo dimensionado para 3 viviendas, y cada vivienda se reparte lo que queda del útil de planta tras esa resta.
2. Edificio de 1 vivienda/planta (unifamiliar o cabecera de escalera ya resuelta en otra planta): no se reserva núcleo — no hace falta, el propio programa ya lo dice.
3. Vivienda con 3 dormitorios en una parcela estrecha donde no caben los 3 con fachada: se genera igual (no se bloquea la generación), pero se advierte explícitamente cuál dormitorio quedó sin fachada exterior.

## 6. Casos límite

- **Tipologías distintas de "Manzana cerrada"** (torre, adosado, vivienda unifamiliar aislada): el criterio de núcleo compartido puede no aplicar igual — revisar antes de generalizar la misma fórmula de dimensionado a todas.
- **Edificio de una sola planta**: ¿hace falta ascensor? Normalmente no — el núcleo en ese caso puede reducirse a un pasillo distribuidor sin caja de escalera/ascensor completa.
- **Número de viviendas por planta variable entre plantas** (posible desde la segmentación de plantas de Fase 3, esta sesión): ¿el núcleo se dimensiona por la planta con más viviendas y se mantiene constante en todas (más realista estructuralmente — el hueco de escalera no cambia de sitio entre plantas), o varía planta a planta? Este PRD propone la primera opción por ser la única constructivamente coherente, pero requiere decisión explícita antes de implementar.

## 7. Flujo del usuario

1. El arquitecto ya define, en el Programa de Necesidades del Sandbox, el número de plantas y (via `Viviendas objetivo`/mix por tipología) cuántas viviendas caben por planta.
2. Al generar, el backend calcula el tamaño del núcleo **antes** de llamar a Claude — determinístico, no delegado al LLM.
3. Esa superficie se resta del total útil disponible que ya reciben las funciones existentes de reparto (`_build_user_message`, `place_rooms`).
4. Tras generar, una validación geométrica (mismo patrón que `_validate_unit`/`verificar_directivas_duras`, ya existentes) comprueba fachada exterior de salón/dormitorios en cada vivienda y añade advertencias si falla — nunca bloquea la generación.

## 8. Criterios de aceptación

1. Un edificio generado con ≥2 viviendas/planta incluye un núcleo de comunicación + pasillo distribuidor común, visible como estancia(s) propia(s) en el plano 2D resultante.
2. La superficie total repartida entre las viviendas de esa planta es el útil declarado MENOS la superficie del núcleo — verificable sumando m² de todas las estancias generadas.
3. Un edificio de 1 vivienda/planta no cambia de comportamiento respecto a hoy — cero regresión.
4. Toda estancia salón/dormitorio de cada vivienda generada, en un lote de prueba, tiene fachada exterior o aparece listada en `advertencias` explicando cuál no la tiene.

## 9. Riesgos

- **`ai_generator.py` es una pieza sensible**: el propio código de `app.py` señala varias veces que está "fuera de alcance" para otras tareas — tocarlo aquí exige cuidado de no romper el prompt/las validaciones ya existentes (pasillo interno por vivienda, Dormitorio 1 en fachada, reintento único ante geometría fallida).
- **El tamaño "razonable" de un núcleo es, en el fondo, una decisión normativa real** (CTE DB-SUA accesibilidad, dimensiones mínimas de escalera protegida/foso de ascensor) que hoy no está confirmado que exista como corpus verificado en este proyecto. Fijar una cifra sin esa base es fabricar precisión que no existe — mismo riesgo que ya se evitó explícitamente en el checklist de campo (`docs/prd/2026-08-16-checklist-inspeccion-campo.md`, §0) y en el Programa de Necesidades (superficie mínima de vivienda "por tipología, no por comunidad autónoma, hasta que el corpus territorial esté poblado").
- Compite por tiempo con lo ya priorizado en `REFACTOR_MASTERPLAN.md`.

## 10. Impacto sobre módulos existentes

- `analyzer/ai_generator.py`: nueva función determinista de dimensionado de núcleo (llamada antes de `_call_claude`); ajuste de la superficie útil que se comunica al prompt/al ajuste geométrico posterior; nueva validación de fachada exterior tras generar.
- `analyzer/evaluator.py`: posible regla nueva de fachada exterior si no existe ya una equivalente ahí (revisar antes de duplicar lógica).
- `app.py`: ningún cambio de contrato esperado en `/api/generar` — el núcleo es un efecto interno del generador, no un parámetro nuevo que el arquitecto tenga que rellenar.
- Ningún cambio en `static/programa-necesidades.js` — el número de viviendas/planta que ya captura ese formulario es el único dato de entrada que hace falta, no requiere campos nuevos.

## 11. Plan de implementación dividido en pequeñas tareas

1. Función determinista de dimensionado de núcleo (superficie de ascensor + escalera + distribuidor, en función del nº de viviendas/planta) — sin corpus normativo verificado todavía, marcar explícitamente como estimación razonada, no como cifra CTE confirmada (ver §14).
2. Restar esa superficie del útil distribuible antes de construir el mensaje a Claude / antes de `place_rooms`.
3. Representar el núcleo como estancia(s) propia(s) en el resultado generado (mismo modelo `Room`/`Unit` que ya existe).
4. Validación de fachada exterior por vivienda tras generar, reutilizando el patrón de `advertencias` ya existente.
5. Verificación en vivo: generar un edificio de 3 viviendas/planta y uno de 1 vivienda/planta sobre la misma tipología; comprobar los 4 criterios de §8.

## 12. Plan de pruebas

- `python -m py_compile analyzer/ai_generator.py`.
- Lote de generación de prueba (varias combinaciones de nº de viviendas/planta) comprobando presencia de núcleo, resta de superficie correcta, y advertencias de fachada cuando corresponda.
- Regresión: un edificio de 1 vivienda/planta generado antes y después de este cambio debe dar el mismo resultado.

## 13. Métricas para medir el éxito

- % de proyectos generados con ≥2 viviendas/planta que incluyen núcleo de comunicación dimensionado (objetivo: 100%).
- % de estancias salón/dormitorio con fachada exterior confirmada tras generar (objetivo: 100%, con advertencia explícita en el resto — nunca un incumplimiento silencioso).

## 14. Posibles motivos para NO implementar la idea

- **El corpus normativo de dimensiones mínimas de núcleo no está confirmado que exista ya en este proyecto.** Si no existe, cualquier cifra que se fije aquí es una estimación razonada, no un dato normativo verificado, y debe marcarse como tal — mismo criterio que ya se aplicó explícitamente en Fase 1 de esta sesión ("perfil de ejemplo, marcado como tal") para no presentar como real algo que no lo es.
- **Alternativa de menor riesgo**: implementar primero solo la reserva de superficie del núcleo (auto-consistente — no depende de ninguna normativa externa, solo de que exista un hueco proporcional al nº de viviendas) y la validación de fachada (criterio geométrico duro, tampoco depende de normativa), dejando el dimensionado normativo estricto del núcleo (ancho mínimo de escalera protegida, foso de ascensor real) para una iteración posterior, cuando exista ese corpus verificado. Evita tocar `ai_generator.py` dos veces por el mismo motivo.

---

**Decisión:** _pendiente de revisión por Pablo_
