# PRD — Sólido Capaz persistente y encaje del edificio generado en el visor 3D

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: "en el visor de edificio completo... la geometría aparece desubicada en un plano negro infinito sin terreno ni parcela" y pide que "la escala y posición del volumen 3D generado por el motor de plantas encaje exactamente sobre la masa del Sólido Capaz de la parcela seleccionada".

Verificado en vivo antes de escribir esto (parcela real, RC 24205A90400146, León, con Paso 0 + Sólido Capaz calculados en el Sandbox): el Sandbox (`viewer-sandbox.js`) renderiza terreno/huella/sombras correctamente — no está roto. El problema real es otro: **`viewer-edificio.js` ("Edificio completo") es un visor totalmente independiente**, con su propio terreno decorativo genérico (rejilla oscura + árboles fijos, `viewer-edificio.js:854-899`), que solo carga foto/colindantes reales si el proyecto tiene sitio enlazado (`cargarEntornoUrbano`) — y que **no tiene ningún concepto de Sólido Capaz**. Ese dato se calcula y vive enteramente en memoria del Sandbox (`solidoCapazMesh`, `viewer-sandbox.js:958`); nunca se guarda en el proyecto ni llega a ningún otro visor. "Generar plantas con IA" desde el Sandbox, además, no genera nada ahí mismo: saca al arquitecto a un formulario aparte (`Modo experto`/entrevista) que crea un proyecto nuevo sin relación con la sesión de Sandbox que lo originó.

Así que no es una corrección de escala/posición sobre algo que ya existía — es una integración que nunca se construyó entre dos módulos hasta ahora deliberadamente separados. De ahí este PRD.

## 1. Problema que resuelve

Un arquitecto que ya invirtió tiempo en el Sandbox (parcela real, límites urbanísticos, Sólido Capaz calculado) no tiene ninguna forma de comprobar, una vez generado el edificio con IA, si el resultado cabe de verdad dentro de la envolvente legal que él mismo definió. Tiene que comparar cifras sueltas (HUD del Sandbox vs. datos del proyecto generado) a mano, sin ninguna vista que las superponga. `ROADMAP_VISION_ARQUITECTONICA.md` sitúa el cierre del círculo urbanismo→diseño como un pilar explícito; hoy ese círculo se rompe justo en la costura entre el Sandbox y el generador.

## 2. Usuario afectado

El arquitecto que completa Paso 0 (parcela real) y calcula el Sólido Capaz en el Sandbox **antes** de generar un proyecto con IA sobre esa misma parcela. No afecta a quien genera directo (sin pasar por el Sandbox) ni a proyectos analizados desde un DXF.

## 3. Objetivo de negocio

Evita que un arquitecto entregue, sin saberlo, un volumen que excede su propia envolvente legal — un fallo de confianza serio para una herramienta que se vende como verificación normativa, no solo como generador de dibujos. Refuerza el moat del producto en la pieza que `MOAT_ANALYSIS.md` señala como más defendible: la lectura normativa real, no la generación en sí (que cualquiera con acceso a un LLM puede replicar).

## 4. Objetivo técnico

Al abrir "Edificio completo" (`viewer-edificio.js`) de un proyecto generado sobre una parcela con Sólido Capaz calculado en el Sandbox:

1. El visor muestra el mismo terreno técnico + huella catastral real que el Sandbox (reutilizando `viewer-terreno.js`, que ya es compartido entre ambos módulos desde el 2026-08-17 — ver comentario en `viewer-edificio.js:37-42`).
2. Se añade una malla translúcida de referencia con la envolvente del Sólido Capaz (mismo polígono/altura calculados en el Sandbox).
3. El edificio generado se posiciona en el **mismo sistema de coordenadas local** (metros este/norte desde el centro real de la parcela) que usa el Sólido Capaz — no en un sistema centrado en el propio bounding box del edificio, que es lo que hace hoy (`viewer-edificio.js:800-802`, `box.getCenter()`).

Si el proyecto no tiene Sólido Capaz calculado (la mayoría de casos hoy), el visor se comporta exactamente igual que ahora — esta capacidad es aditiva, nunca bloqueante.

## 5. Casos de uso

1. Arquitecto calcula un Sólido Capaz de 4 plantas en el Sandbox, genera un edificio de 3 viviendas sobre esa misma parcela, abre "Edificio completo" → ve el edificio real dentro de la envolvente translúcida, con terreno y huella reales debajo.
2. Arquitecto genera un proyecto sin pasar antes por el Sandbox → visor idéntico al actual (terreno genérico decorativo), sin ningún cambio de comportamiento.
3. El volumen generado excede la envolvente legal (más plantas u ocupación de las permitidas) → se muestra igual, sin ocultar ni corregir el dato — se nota visualmente que sobresale de la malla translúcida, mismo criterio de honestidad que la capa roja de exceso del Programa de Necesidades (Fase 3, esta sesión: nunca alterar el dato real, solo visualizarlo).

## 6. Casos límite

- **Sitio real sin Sólido Capaz calculado** (el arquitecto saltó directo a "Generar plantas con IA" sin pasar por el Sandbox): no hay envolvente que mostrar — el visor no inventa una.
- **Sólido Capaz recalculado después de generar el edificio** (el arquitecto cambia límites urbanísticos y vuelve a calcular en el Sandbox tras ya haber generado plantas): la envolvente persistida junto al proyecto queda desactualizada respecto al último cálculo. Decisión pendiente (§14): ¿se persiste como snapshot del momento de generación (más simple, puede quedar obsoleta) o se recalcula bajo demanda al abrir el visor (más correcto, exige repetir la lógica de `calcularSolidoCapaz` fuera del Sandbox)? Este PRD propone snapshot con aviso de fecha, por ser la opción más barata y menos frágil — ver Plan de implementación.
- **Parcela sin geometría real de Catastro** (como el caso de León usado para verificar este PRD): igual que hoy, sin huella real, solo terreno genérico — el Sólido Capaz tampoco tendría un polígono real del que partir en ese caso.

## 7. Flujo del usuario

1. Arquitecto completa Paso 0 (parcela real) y calcula Sólido Capaz en el Sandbox.
2. Pulsa "Generar plantas con IA" → el formulario de generación (Modo experto/entrevista) se abre con la referencia catastral ya rellenada y — nuevo — el Sólido Capaz calculado adjunto como contexto (polígono final en metros locales, altura máxima, plantas legales, superficie ocupada).
3. Al generar (`POST /api/generar`), el backend persiste ese Sólido Capaz junto al proyecto nuevo.
4. Al abrir "Edificio completo", si el proyecto tiene `solido_capaz` guardado, el visor construye terreno técnico + huella real (vía `viewer-terreno.js`) y añade la malla translúcida de la envolvente, en el mismo origen de coordenadas que el edificio generado.

## 8. Criterios de aceptación

1. Un proyecto generado con Sólido Capaz previo muestra, en "Edificio completo", el mismo terreno circular + huella real que el Sandbox de origen — verificado comparando ambos visores con la misma parcela.
2. La malla translúcida de la envolvente aparece en la posición y escala correctas (mismo centro/orientación que la parcela real), sin desplazamiento respecto al edificio generado.
3. Un proyecto generado SIN Sólido Capaz previo se comporta exactamente igual que hoy — cero regresión, verificado con un proyecto existente.
4. Si el volumen generado excede la envolvente, el exceso es visualmente perceptible sin que ningún número (ocupación, edificabilidad, plantas) se altere respecto a lo que ya calcula el Sandbox.

## 9. Riesgos

- **Coordinar dos sistemas de coordenadas hoy independientes es el riesgo técnico central.** `viewer-edificio.js` centra la escena en el bounding box del propio edificio (`box.getCenter()`); el Sólido Capaz usa el centro real de la parcela. Un error aquí produce el mismo síntoma que hoy pero silencioso: todo "parece" encajar en la vista por defecto pero está en la posición equivocada en términos absolutos — más difícil de detectar que el vacío negro actual.
- **Alcance no trivial**: nueva columna de persistencia, nuevo tramo de payload en `/api/generar`, refactor parcial del posicionamiento de `viewer-edificio.js`. No es una corrección de una tarde.
- Compite por tiempo con lo que ya esté priorizado en `REFACTOR_MASTERPLAN.md` — revisar antes de planificar la implementación.

## 10. Impacto sobre módulos existentes

- `analyzer/storage.py`: columna nueva `solido_capaz` en la tabla `proyectos` (mismo patrón que las columnas `modelo`/`traza_generacion` ya existentes — JSON, nullable, migración idempotente, nunca dentro de `payload`).
- `app.py`: `/api/generar` acepta un campo opcional `solido_capaz` en el body y lo persiste si viene; el detalle de proyecto (`GET /api/proyectos/<id>`) lo devuelve si existe.
- `static/viewer-sandbox.js`: serializar el Sólido Capaz calculado (polígono final, altura, plantas legales) al invocar "Generar plantas con IA".
- `static/entrevista.js` / formulario "Modo experto": transportar ese dato hasta el `POST /api/generar` sin que el arquitecto tenga que volver a introducirlo.
- `static/viewer-edificio.js`: consumir `solido_capaz` si existe, reutilizar `viewer-terreno.js` para huella/terreno reales, unificar el origen de coordenadas con el que usa el Sólido Capaz.
- Ningún cambio en `evaluator.py` ni en el propio cálculo del Sólido Capaz (`viewer-sandbox.js`) — se reutiliza tal cual, solo se serializa.

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/storage.py`: columna `solido_capaz`, `guardar_proyecto()`/`obtener_proyecto()` la leen/escriben.
2. `viewer-sandbox.js`: función de serialización del Sólido Capaz activo (o `null` si no se ha calculado).
3. Transporte del dato desde el Sandbox hasta `POST /api/generar` (vía el formulario de generación).
4. `app.py`: aceptar y persistir el campo en `/api/generar`; devolverlo en el detalle de proyecto.
5. `viewer-edificio.js`: si `proyecto.solido_capaz` existe, construir terreno/huella real (reutilizando las mismas funciones que ya usa cuando hay sitio real) y la malla translúcida de la envolvente.
6. `viewer-edificio.js`: unificar el sistema de coordenadas del edificio generado con el centro real de la parcela (en vez de `box.getCenter()`), solo cuando hay sitio real vinculado — sin tocar el caso sin sitio real.
7. Verificación en vivo: los 4 criterios de aceptación de §8, con la misma parcela usada para diagnosticar este PRD.

## 12. Plan de pruebas

- `node --check` sobre los archivos JS tocados.
- `python -m py_compile app.py analyzer/storage.py`.
- En vivo: generar un proyecto con Sólido Capaz previo y otro sin él sobre la misma parcela real; comparar ambos "Edificio completo"; comprobar que el proyecto sin Sólido Capaz no cambia de comportamiento.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma, mirando el visor, que el edificio generado se lee de forma inequívoca como "dentro" o "fuera" de su propia envolvente legal, sin tener que consultar ningún número aparte.

## 14. Posibles motivos para NO implementar la idea

- **Coste de integración alto para un flujo que puede ser minoritario hoy**: si la mayoría de proyectos se generan sin pasar antes por el Sandbox, el ROI de esta pieza es bajo frente a su coste (nueva columna, nuevo payload, refactor de coordenadas). Antes de planificarlo valdría la pena que Pablo confirme cuánto se usa hoy el flujo Sandbox → Generar plantas con IA en el mismo proyecto.
- **Alternativa más barata y de menor riesgo**: no tocar el sistema de coordenadas de `viewer-edificio.js` (el riesgo técnico más alto de este PRD) y quedarse solo con la parte "casi gratis" — mostrar terreno/huella reales cuando el proyecto tiene sitio vinculado (el dato ya se pide vía `entorno-3d`, ver `viewer-edificio.js:1077`) sin la malla translúcida del Sólido Capaz. Deja la comparación de encaje como lo que ya es hoy: una lectura manual de los números del HUD del Sandbox, que ya son correctos, solo no están dibujados uno encima del otro. Recomiendo empezar por aquí si se prioriza esto, y dejar la malla translúcida (y la unificación de coordenadas que exige) para una segunda iteración una vez validado que el encaje es correcto.

---

**Decisión:** _pendiente de revisión por Pablo_
