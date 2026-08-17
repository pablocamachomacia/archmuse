# PRD — Normativa urbanística en capas (WMS autonómico + tabla local + formulario manual)

**Estado:** Fase A aprobada e implementada; Fase B/C sin empezar · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-17, solo Fase A)

**Fase A implementada (2026-08-17)** con estas decisiones explícitas de Pablo, más estrictas que la
propuesta original de este documento: panel de límites SIEMPRE expandido (no colapsado tras un
`<details>`); los 4 campos (ocupación, altura, retranqueos, edificabilidad — "Plantas máx." queda
fuera, no es uno de los 4) con placeholders "ej. X" cuando están vacíos; persistencia en
`localStorage` por `"normativa_" + referencia_catastral`, tiempo real vía evento `input`, sin botón
"Aplicar"; **cero texto explicando por qué no se detectó normativa** (se retiró el aviso
`datos.motivo` que sí existía antes) — la única señal ahora es que los campos aparecen vacíos.
Fase B (tabla de zonas) y Fase C (WMS) siguen sin empezar, tal cual quedaron documentadas abajo.

---

## 0. Nota de alcance (léase antes que el resto)

El encargo de Pablo parte de una premisa que hay que corregir primero: **"el panel de Urbanismo solo cubre la Norma Zonal 1.5 de Madrid" no es del todo exacto.** Verificado leyendo `analyzer/normativa_madrid.py` y el PRD que lo implementó (`docs/prd/2026-08-16-integracion-normativa-catastro-pgou.md`, §15, "Cierre"): **hoy no hay NINGUNA zona, ni siquiera Madrid Norma Zonal 1.5, con los 4 números reales** (`ocupacion_maxima_pct`/`edificabilidad_maxima`/`plantas_maximas`/`retranqueos_m`). `limites_numericos` es `SIEMPRE None` en el código actual — a propósito. Lo que sí hay para Madrid 1.5 es **referencia real** (grado, manzana, coeficiente) mostrada como contexto, con una nota explícita de que faltan los números.

La razón, ya investigada y documentada en el PRD anterior, no es pereza: `COND_EDIF`/`COEF_Z` son códigos que remiten a la letra de la normativa impresa, no números; y — hallazgo más grave — **la propia Norma Zonal 1 (la única con datos reales hoy) ni siquiera se regula con el modelo ocupación/edificabilidad/retranqueos** (usa "fondo edificable + coeficiente ponderado", altura por cornisas colindantes con aprobación de la CIPHAN). El servicio que resolvería "en qué Norma Zonal está un punto cualquiera de Madrid" (`PG_ORDENACION`) lleva caído desde antes de esa investigación.

**Esto cambia el punto de partida real de este PRD**: no es "expandir una cobertura que funciona" a más zonas y ciudades — es "todavía no hay ninguna zona con números automáticos fiables, y el encargo de hoy pide llegar a 3 ciudades y ~17 zonas a la vez". Evaluado contra `ROADMAP_VISION_ARQUITECTONICA.md` §3.2 (cita literal): *"El asesor urbanístico real es una apuesta de años de datos, no de un sprint"* — y su §6 ya fija la secuencia recomendada: **un único municipio real y verificado primero (Madrid), ampliar a 2-3 municipios más solo después, con el mismo criterio de verificación manual antes de automatizar.** El encargo de hoy salta directamente a 3 ciudades y una capa WMS "por comunidad autónoma" (17 servicios distintos, cada uno con su propio formato/fiabilidad, ninguno investigado todavía) en un solo PRD. Este documento separa las 3 capas pedidas y da una recomendación de secuencia distinta a la literal — ver §14.

## 1. Problema que resuelve

Fuera de Madrid (y, en la práctica, incluso dentro de Madrid — ver §0), el panel de Urbanismo del Sandbox no ofrece ningún valor por defecto: el arquitecto tiene que rellenar a mano ocupación/edificabilidad/retranqueos/plantas sin ninguna ayuda contextual, ni siquiera un "esto es lo que se suele usar en tu zona". Petición directa de Pablo.

## 2. Usuario afectado

El arquitecto que trabaja sobre una parcela real fuera de Madrid (o dentro de Madrid pero en una zona no cubierta hoy — la mayoría), que hoy no tiene ningún punto de partida para los límites urbanísticos y tiene que buscarlos por su cuenta en el geoportal de su municipio antes de poder usar el Sandbox con datos realistas.

## 3. Objetivo de negocio

Coherente con `MOAT_ANALYSIS.md` (Pilar 7, ya citado en el PRD anterior): la profundidad normativa real es una cuña de entrada que cuesta meses replicar bien — precisamente porque no es una API sencilla. El riesgo de negocio simétrico, señalado en `DESTROY_ARCHMUSE.md` §5 y ya invocado en el PRD anterior, es igual de real: **"un hallazgo normativo incorrecto no se perdona una segunda vez"**. Este PRD debe equilibrar ambos, no solo perseguir cobertura.

## 4. Objetivo técnico

Para una coordenada real, resolver los límites urbanísticos por el primer camino que dé un resultado fiable, en este orden:
1. Consulta automática a un servicio WMS/REST municipal o autonómico real, verificado.
2. Tabla local de valores numéricos, verificados a mano contra el texto oficial de la normativa vigente.
3. Formulario manual, siempre disponible, nunca bloqueante.

Ningún número se presenta como "automático" si no se ha verificado contra la fuente oficial — mismo criterio ya aplicado en `cte_zonas.py` y en el PRD anterior de normativa.

## 5. Casos de uso

1. Parcela en una zona con tabla local verificada → los 4 campos se rellenan automáticamente, editables, con etiqueta de fuente y fecha de verificación.
2. Parcela en un municipio con WMS real integrado y verificado, sin traducción numérica todavía → se muestra la referencia real (como ya hace Madrid 1.5), no los 4 números.
3. Parcela sin ninguna cobertura automática (el caso más común hoy, fuera de Madrid) → aparece el formulario manual de Capa 3, sin ningún aviso de error.
4. Arquitecto ya había escrito valores a mano cuando llega una respuesta automática tardía → el valor manual no se sobrescribe (mismo criterio ya vigente en el PRD anterior, §6).

## 6. Casos límite

- Punto en el límite entre dos zonas: mismo criterio ya definido en el PRD anterior (§6) — se toma el primer resultado, con aviso de "verifica en el límite de zona".
- Servicio WMS autonómico caído o con formato distinto al esperado: nunca un error técnico visible — degrada a Capa 2, y si tampoco hay tabla local, a Capa 3. Igual que hoy con Madrid.
- Zona presente en la tabla local pero con un campo sin dato real verificado (p. ej. una ordenanza que no fija edificabilidad): ese campo concreto se deja vacío/editable, nunca en 0 inventado — mismo criterio que `evaluator.py` ya aplica cuando `limites_numericos` es `None`.
- Comunidad autónoma sin ningún WMS público conocido todavía (la mayoría, sin investigar): se trata igual que "Capa 1 no disponible aquí", cae directa a Capa 2/3 — nunca se bloquea el Sandbox esperando una integración que no existe.

## 7. Flujo del usuario

1. Al abrir el Sandbox con una parcela real, se lanza en paralelo (no bloqueante, mismo patrón que `pedirNormativaUrbanisticaPunto` ya existente) la resolución en cascada: Capa 1 → Capa 2 → Capa 3.
2. Si Capa 1 o Capa 2 resuelven los 4 números: se rellenan como valores por defecto editables, con fuente y fecha visibles.
3. Si solo hay referencia real sin traducción numérica (caso Madrid 1.5 hoy): se muestra como contexto, igual que ahora.
4. Si nada resuelve: aparece el formulario de Capa 3 ya expandido (no un `<details>` colapsado), con el texto "Introduce los límites de tu ordenanza", sin iconos ni color de alerta.
5. El arquitecto edita cualquier campo en cualquier momento; ninguna respuesta tardía sobrescribe un campo ya tocado.

## 8. Criterios de aceptación

- [ ] Capa 3 (formulario manual): aparece automáticamente, expandido, con los 4 campos pedidos (`Ocupación máxima (%)`, `Altura máxima (m)`, `Retranqueos (m)`, `Edificabilidad (m²/m²)`) y el texto exacto pedido, sin alertas ni colores de error, cuando ninguna capa superior resuelve datos.
- [ ] Capa 2: para cada zona añadida a la tabla local, el valor coincide, verificado a mano contra el texto oficial de la ordenanza vigente (no una aproximación de memoria) — igual que exigía el PRD anterior (§8.1) para Madrid.
- [ ] Capa 1: para cada servicio WMS/REST integrado, spike de verificación en vivo ANTES de escribir código de producto (mismo criterio que el PRD anterior, §11 Tarea 1) — nunca se integra un servicio sin confirmar antes que responde con datos reales y utilizables para el modelo `evaluator.py`.
- [ ] Cero regresión sobre Madrid 1.5 (referencia real ya funcionando) ni sobre el resto del Sandbox.
- [ ] Nunca se muestra un mensaje de error técnico al usuario, en ningún camino de fallo — mismo criterio ya vigente.

## 9. Riesgos

- **El riesgo central, heredado directamente del PRD anterior y no resuelto por éste**: rellenar la tabla local (Capa 2) con valores no verificados contra el texto oficial de cada ordenanza sería exactamente "presentar un dato automático incorrecto como si fuera fiable" — el riesgo que ese PRD identificó como el más grave de todo el proyecto en esta área. **Yo (como autor de este PRD) no tengo forma de verificar con certeza, desde aquí, valores reales de ocupación/edificabilidad/altura/retranqueos para las ~17 zonas de Madrid/Barcelona/Valencia que pide el encargo** — necesitaría, para cada una, el texto vigente de la ordenanza (PGOU de cada municipio, con sus normas urbanísticas específicas) verificado punto por punto, exactamente como se hizo para investigar Madrid 1.5 (y aun así, esa investigación concluyó que ni siquiera esa zona tiene traducción numérica honesta posible). Escribir la tabla sin ese trabajo sería inventar.
- **Capa 1 (WMS por comunidad autónoma) es una apuesta mucho mayor de lo que suena**: cada comunidad autónoma (17) publica su propio geoportal, con su propio formato (WMS/WFS/ArcGIS REST/otro), su propia cobertura y su propia fiabilidad — la investigación de Madrid (un solo ayuntamiento) ya reveló 2 servicios caídos y una capa con nombre engañoso. Extrapolar ese esfuerzo a 17 CCAA sin investigación previa no es una tarea de "un par de horas", es del orden de magnitud de meses que ya advertía `MOAT_ANALYSIS.md`.
- **Servicios municipales/autonómicos sin SLA conocido** (ya observado en vivo con Madrid: `"Service not started"`) — cada nueva integración hereda el mismo riesgo de disponibilidad, multiplicado por el número de servicios.
- **Compite directamente con el resto del roadmap** (`REFACTOR_MASTERPLAN.md`) y con la secuencia ya recomendada en `ROADMAP_VISION_ARQUITECTONICA.md` §6, que pide ampliar de uno a 2-3 municipios **después**, no simultáneamente con 3 ciudades y una integración autonómica genérica.

## 10. Impacto sobre módulos existentes

- `analyzer/normativa_madrid.py` → se generaliza a `analyzer/normativa_urbanistica.py` (o se añaden módulos hermanos por municipio, a decidir en implementación) con una función de resolución en cascada (Capa 1 → Capa 2 → `disponible: False` para que el cliente muestre Capa 3).
- **Nuevo**: tabla local de zonas verificadas (Capa 2) — estructura de datos versionada en el repo, auditable, con fecha de verificación por entrada (mismo criterio que `cte_zonas.py`).
- `app.py`: el endpoint `/api/normativa-urbanistica-punto` ya existe — cambia su implementación interna, no su contrato con el cliente.
- `static/viewer-sandbox.js`: el panel "Límites urbanísticos" ya existe (`construirHudUrbanismo`, `<details>` colapsado con 4 campos: ocupación, retranqueos, edificabilidad, **plantas** — no altura en metros). Cambios: (a) añadir/sustituir el campo de plantas por "Altura máxima (m)" si se confirma que es el campo que de verdad pide el encargo, revisando el impacto en `evaluator.py` (que hoy usa `plantas_maximas`, no metros — reconciliar antes de tocar); (b) expandir automáticamente (no colapsado) con el texto pedido cuando ninguna capa superior resuelve datos; (c) quitar cualquier estilo de alerta si lo hubiera (ya se revisó en la limpieza de UI de esta misma sesión — hoy no lo tiene).
- `analyzer/evaluator.py`: sin cambios de lógica si Capa 2 devuelve el mismo formato de `normativa` que ya consume.

## 11. Plan de implementación dividido en pequeñas tareas

**Fase A — Capa 3 (barata, sin riesgo de dato incorrecto, entrega valor inmediato):**
1. Reconciliar "Altura máxima (m)" del encargo vs. "Plantas máx." que ya existe en el HUD y en `evaluator.py` — decisión con Pablo antes de tocar código (puede que haga falta un campo nuevo y una conversión, no una sustitución).
2. Panel expandido automáticamente (no `<details>` colapsado) con el texto exacto pedido, cuando `disponible: false` en la respuesta del endpoint — sin alertas ni colores de error.
3. Verificación en vivo: parcela sin ninguna cobertura (la mayoría hoy) muestra el formulario limpio, sin mensajes de error.

**Fase B — Capa 2, solo para las zonas que Pablo pueda verificar de verdad (empezar por 1, no por 17):**
4. Definir con Pablo, ANTES de escribir la tabla, de dónde sale cada número: ¿Pablo aporta los valores con su propia verificación profesional (lo más rápido y fiable), o hace falta que yo investigue el texto oficial de cada ordenanza (lento, y con el mismo riesgo que ya se documentó para Madrid)?
5. Tabla local para la primera zona acordada, con fecha de verificación y fuente citada — mismo patrón que `cte_zonas.py`.
6. Integrar en la cascada de resolución; verificar en vivo contra un caso real de esa zona.
7. Repetir 5-6 zona por zona, nunca en bloque, según prioridad real de proyectos de Pablo.

**Fase C — Capa 1, solo si Fase B demuestra que merece la pena automatizar (spike primero, siempre):**
8. Para el PRÓXIMO municipio (no comunidad autónoma entera) que Pablo priorice, repetir el spike de investigación en vivo que ya se hizo para Madrid (§11 Tarea 1 del PRD anterior) — confirmar que el servicio existe, responde, y resuelve zona+valores antes de comprometerse.
9. Cliente + endpoint + integración en el panel, mismo patrón que Madrid.

## 12. Plan de pruebas

- Cada entrada de la tabla local (Capa 2), verificada a mano contra el documento oficial de la ordenanza — captura/cita de la fuente guardada junto al dato, mismo estándar que el PRD anterior exigía para Madrid (§12).
- Cada servicio WMS/REST nuevo (Capa 1): spike documentado antes de integrar, igual que Madrid.
- Simulación de fallo en cada capa (servicio caído, zona no encontrada) → confirmar que se degrada silenciosamente a la capa siguiente, nunca un error visible.
- `python -m py_compile` sobre los módulos nuevos; `node --check` sobre los cambios de `viewer-sandbox.js`.

## 13. Métricas para medir el éxito

Igual que el PRD anterior: cualitativo, no de volumen. Un solo valor verificado incorrecto en producción es motivo de retirarlo, no de "aceptar una tasa de error". El éxito de Capa 3 es que un arquitecto sin cobertura automática ya no ve una pantalla vacía, sino un punto de partida limpio.

## 14. Posibles motivos para NO implementar la idea (o para implementarla distinto)

- **El encargo tal y como está escrito (WMS por comunidad autónoma + tabla de 17 zonas en 3 ciudades, en un solo PRD) repite el mismo error que `ROADMAP_VISION_ARQUITECTONICA.md` §6 ya advierte evitar**: prometer cobertura amplia de normativa real sin el trabajo de verificación manual que cada zona exige. La investigación de Madrid — UN municipio, UNA norma zonal — ya reveló que ni siquiera esa zona tiene traducción numérica honesta posible hoy. Multiplicar eso por 17 no es viable en un solo incremento.
- **Recomendación real de este PRD, distinta de la petición literal**: implementar SOLO la Fase A (Capa 3, formulario manual) ahora — es barata, cero riesgo de dato incorrecto, y resuelve el dolor real inmediato ("hoy no hay ningún punto de partida fuera de Madrid"). Dejar Capa 2 para zona por zona, priorizada por los proyectos reales de Pablo, con él aportando o verificando cada valor — no yo inventándolos. Dejar Capa 1 (WMS autonómico) aparcada hasta que Capa 2 demuestre, con 2-3 zonas reales, que automatizar merece la pena frente al coste de verificación manual — y, aun así, empezar por el SIGUIENTE MUNICIPIO, no por una comunidad autónoma entera de golpe.
- **Alternativa más barata para Capa 1/2 combinadas**: en vez de intentar automatizar 17 servicios distintos, un enlace directo al geoportal urbanístico oficial de cada municipio (cuando se conozca) desde el propio formulario de Capa 3 — cero riesgo de dato mal traducido, aporta contexto real con una sola línea de código.

---

**Decisión:** _pendiente de revisión por Pablo_
