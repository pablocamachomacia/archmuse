# PRD — Checklist de inspección en campo (visita a parcela)

**Estado:** Implementado · **Fecha:** 2026-08-16 · **Fecha de cierre:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (ejecución directa)

---

## 0. Resumen para decidir rápido

Ejecuta `ROADMAP_VISION_ARQUITECTONICA.md` §3.3/§6.2: "la pieza de mayor valor por menor coste" de las cuatro que pedía el encargo original de visión (junto a hiperrealismo/asesor urbanístico/navegación) — no necesita simulación, no necesita datos externos nuevos, no compite con `REFACTOR_MASTERPLAN.md`.

**El encargo pide "implementación rápida" saltándose el PRD — mantengo el proceso** (regla de `CLAUDE.md`, sin excepción para "rápido"), pero el PRD en sí es deliberadamente corto: es una capacidad pequeña y acotada, no hace falta que el documento sea largo para que exista.

**Corrección de encuadre sobre el encargo:** el encargo pide `generar_checklist_campo(datos_parcela)` "según superficie, municipio, orientación y entorno" — esos datos YA existen hoy, pero repartidos entre dos sitios: `proyecto` (guardado, `ciudad`/`tipologia`/`zona_cte`/`norte_grados`) y `sitio` (guardado aparte, vía `obtener_sitio_de_proyecto`, con `superficie_m2`/`colindantes`/`viales`/`zonas_verdes` de Catastro/Overpass — mismo patrón que ya reutiliza `/api/proyectos/<id>/entorno-3d`, `app.py:1363-1389`). No hay que inventar ninguna fuente nueva de datos, solo juntar las dos que ya existen.

**Lo que este checklist NO hace, explícitamente:** no calcula pendientes del terreno, no calcula viento dominante, no calcula impacto acústico real, no verifica vegetación protegida. Nada de eso existe hoy en ArchMuse ni hay ninguna fuente de datos real para ello — el checklist es una **guía de comprobación para el arquitecto en el terreno**, no una nueva verificación automática. Cuando hay un dato real disponible (superficie de Catastro, colindantes con altura, vías cercanas, zona climática), el ítem lleva una nota informativa con ese dato; cuando no lo hay, el ítem es solo el recordatorio de qué comprobar in situ. Presentarlo de otra forma sería inventar precisión que no existe — mismo criterio que ya aplica `evaluator.get_missing_data_warnings` en el resto del producto.

## 1. Problema que resuelve

`DESTROY_ARCHMUSE.md` §4 lo señala como una frustración sin resolver por nadie del sector, ni siquiera por un competidor con 50M€: "nadie cierra el círculo con la fase de obra... la visita física a la parcela sigue sin ninguna guía sistemática." `NORTH_STAR_2031.md` ya lo anticipa en su horizonte de 24 meses ("la aplicación de campo de ArchMuse"). Hoy, cuando un arquitecto visita la parcela física antes o durante el proyecto, no tiene ninguna guía de ArchMuse que llevar — improvisa una lista propia o no sistematiza nada.

## 2. Usuario afectado

El arquitecto que ya tiene un proyecto (generado o analizado) en ArchMuse y necesita visitar la parcela física — antes de cerrar el diseño, o para confirmar que lo dibujado coincide con la realidad del terreno.

## 3. Objetivo de negocio

Barato, aditivo, y encaja en el ciclo diseño→obra que `DESTROY_ARCHMUSE.md` §3 identifica como diferencial de largo plazo. No requiere simulación ni datos externos nuevos — reutiliza lo que Catastro/Overpass ya trajeron para ese proyecto.

## 4. Objetivo técnico

- Dado un proyecto guardado, generar una lista de comprobación en 4 bloques, cada ítem con texto fijo y (cuando hay dato real disponible) una nota contextual derivada de datos reales del proyecto/sitio — nunca un dato inventado.
- La lista es la misma estructura tanto si el proyecto tiene sitio real enlazado como si no (Laboratorio/DXF sin Paso 0) — degrada a notas genéricas, nunca oculta bloques enteros ni rompe.
- El arquitecto puede marcar ítems como revisados y añadir una nota propia, en pantalla, durante la visita.
- Puede imprimir/exportar la lista para llevarla en papel o en el móvil sin conexión.

## 5. Casos de uso

1. Arquitecto abre un proyecto ya generado con parcela real de Madrid (superficie 500 m², 3 colindantes con altura conocida, 2 vías cercanas) → pulsa "Checklist de visita" en el ribbon → ve los 4 bloques, con notas como "Superficie según Catastro: 500 m² — confirma que coincide con la medición en campo" y "3 edificios colindantes registrados (alturas: 9, 12, 15 m) — valora la sombra que proyectan, especialmente en invierno".
2. El mismo arquitecto, en la parcela, marca 8 de 18 ítems y añade una nota manual en "Muros de contención" ("hay un muro de 1,5 m en el lindero norte, no reflejado en Catastro").
3. Arquitecto con un proyecto del modo Laboratorio (sin parcela real) abre el checklist → ve los mismos 4 bloques, sin ninguna nota contextual (solo los recordatorios genéricos) — nunca un error, nunca un bloque vacío.
4. Arquitecto pulsa "Imprimir" → se abre el diálogo de impresión del navegador con una versión limpia (sin ribbon, sin sidebar) lista para llevar en papel.

## 6. Casos límite

- **Proyecto sin `proyecto_id`** (análisis de un DXF recién subido, todavía no guardado): el botón del ribbon no aparece — mismo criterio ya usado para la pestaña "Mapa" (`data.proyecto_id ? ... : ""`, `app.js:1302`), que depende del mismo requisito.
- **Proyecto guardado sin sitio enlazado** (`obtener_sitio_de_proyecto` devuelve `None`): el checklist se genera igual, con `datos_parcela` reducido a lo que ya tenga `proyecto` (`ciudad`/`tipologia`/`zona_cte`/`norte_grados`, pueden faltar también) — nunca un 404, mismo criterio "no disponible, no error" que el resto de la integración con Catastro/Overpass.
- **`sitio.datos` con `errores`** (p. ej. Overpass falló para colindantes en su momento): los bloques que dependían de ese dato faltante se quedan sin nota contextual, sin mencionar el error técnico (el arquitecto en el terreno no necesita saber que Overpass dio timeout, solo que ese dato no está disponible).
- **Marcar/desmarcar ítems y recargar la página**: el estado de las casillas se pierde (no persistido, decisión explícita de alcance — ver §14). No es una regresión, es lo que dice este PRD desde el principio.
- **Imprimir sin haber marcado nada**: el diálogo de impresión se abre igual, con todas las casillas vacías — es una plantilla válida para llevar en papel y marcar a mano si se prefiere.

## 7. Flujo del usuario

1. Con un proyecto guardado abierto, el arquitecto ve un nuevo botón "Checklist de visita" en el grupo "Campo" del ribbon (pestaña "Vista").
2. Al pulsarlo, se pide `GET /api/proyectos/<id>/checklist-campo` (una vez, cacheado en `state` mientras el proyecto siga abierto) y se abre un overlay a pantalla completa (mismo patrón que `#room-viewer-3d`/`#viewer-sandbox`, no un modal — este proyecto no tiene modales).
3. El overlay muestra los 4 bloques con sus ítems; cada ítem tiene una casilla y, si aplica, una nota contextual en cursiva bajo el texto. Cada ítem tiene además un campo de texto libre opcional ("Nota de campo") para que el arquitecto escriba lo que observa in situ.
4. Marcar una casilla o escribir una nota actualiza el estado en memoria (`state.checklistCampo`), sin llamada de red.
5. Un botón "Imprimir / Exportar" llama a `window.print()`; una hoja de estilos `@media print` oculta el resto de la aplicación y deja solo el contenido del checklist, con las casillas ya marcadas y las notas ya escritas visibles como texto.
6. Cerrar el overlay vuelve al workspace; si se reabre, se vuelve a pedir el checklist al backend (estado de casillas se pierde, §6).

## 8. Criterios de aceptación

Todos verificados en vivo (Chrome, servidor local, 2 proyectos reales guardados) el 2026-08-16.

1. **[x]** El botón "Checklist de visita" existe en el ribbon (grupo "Campo"), solo visible con `proyecto_id` — verificado en dos proyectos guardados distintos.
2. **[x]** `GET /api/proyectos/<id>/checklist-campo` devuelve los 4 bloques con 5 ítems cada uno (20 en total), para un proyecto con sitio real enlazado (`ed901255eeeb`, Madrid, `tiene_sitio_real: true`) y para uno sin él (`d794b44932d7`, DXF, `tiene_sitio_real: false`) — ninguno rompe, ambos devuelven 200 con los 20 ítems.
3. **[x]** Los ítems con dato real muestran ese dato exacto: verificado con notas reales de Catastro ("Superficie según Catastro: 3000 m²…", "Orientación declarada en el proyecto: 90.0°…", "Referencia catastral registrada: 8931006VK2783S."); sin sitio real, ningún ítem inventa un dato (solo 1 nota — la de orientación, que viene del `proyecto` guardado, no del `sitio` — el resto sin nota).
4. **[x]** Marcar/desmarcar casillas y escribir notas de campo funciona en pantalla, sin llamada de red — verificado marcando un ítem (fondo verde) y escribiendo una nota completa sin recarga ni pérdida de foco del textarea.
5. **[x]** "Imprimir / Exportar" invoca `window.print()` (verificado sustituyendo temporalmente `window.print` por un espía, sin llegar a abrir el diálogo nativo real durante la verificación automatizada) y la hoja `@media print` está cargada con sus 6 reglas (`body > :not(#checklist-campo)`, `#checklist-campo`, toolbar oculta, etc.) — confirmado leyendo `document.styleSheets` en vivo.
6. **[x]** Cero regresión: el resto del ribbon (Modos/Encuadre/Paneles), el workspace y las pestañas Modelo/3D/Mapa siguen funcionando; consola sin errores tras la sesión completa de pruebas.

**Bug real encontrado y corregido durante la verificación:** el primer intento reutilizó los tokens de color de tema oscuro del resto de la app (`--text-primary`, `--bg-card`) sobre el fondo claro tipo "papel" de este panel — el título de cada bloque quedaba casi invisible (texto casi blanco sobre fondo claro). Corregido con una paleta propia y autoconsistente para todo el panel (nunca mezclada con los tokens de tema oscuro), documentada en el propio CSS.

## 9. Riesgos

- **Ítems sin nota contextual pueden sentirse "genéricos"** si el proyecto no tiene sitio real enlazado — es el comportamiento correcto (§0/§6), no un defecto, pero merece dejarse claro en la propia UI (un aviso breve: "Sin parcela real enlazada: estas comprobaciones son generales").
- **Ninguno de los 4 bloques puede convertirse, sin querer, en una promesa de verificación automática** que ArchMuse no hace (pendientes reales, viento, acústica, vegetación protegida) — el texto de cada ítem debe leerse inequívocamente como "esto lo compruebas tú en el terreno", nunca como "esto ya lo hemos comprobado nosotros".
- **Estado no persistido**: si el arquitecto cierra el navegador a media visita, pierde lo marcado. Aceptable para una v1 (§14), pero es una limitación real a comunicar, no a ocultar.

## 10. Impacto sobre módulos existentes

- **Nuevo** `analyzer/checklist_campo.py`: función pura `generar_checklist_campo(datos_parcela: dict) -> list[dict]`, sin I/O, fácil de testear con distintos `datos_parcela`.
- `app.py`: nuevo `GET /api/proyectos/<proyecto_id>/checklist-campo`, reutiliza `obtener_proyecto`/`obtener_sitio_de_proyecto` (ya importados), mismo patrón exacto que `proyecto_entorno_3d`.
- `static/index.html`: nuevo overlay `#checklist-campo` (mismo patrón que `#room-viewer-3d`).
- `static/app.js`: nuevo grupo de ribbon "Campo", wiring del botón, `state.checklistCampo`, render del overlay, `window.print()`.
- `static/style.css`: estilos del overlay + `@media print`.
- Ningún cambio en `evaluator.py`, `sitio.py`, ni en los visores 3D.

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/checklist_campo.py`: función pura + los 4 bloques con sus ítems (texto fijo + lógica de nota condicional por dato disponible).
2. `app.py`: endpoint nuevo, reutilizando `obtener_proyecto`/`obtener_sitio_de_proyecto`.
3. `static/index.html`: marcado del overlay.
4. `static/app.js`: botón de ribbon, fetch + cacheo en `state`, render de bloques/ítems, casillas y notas en memoria.
5. `static/style.css`: estilos del overlay + `@media print`.
6. Verificación en vivo: los 6 criterios de §8, con y sin sitio real enlazado, más impresión.

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/checklist_campo.py`.
- `node --input-type=module --check` no aplica (app.js es script clásico) — verificación manual en navegador.
- En vivo: los 4 casos de uso de §5, más los casos límite verificables de §6 (proyecto sin sitio, proyecto sin `proyecto_id` no muestra el botón).

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que la lista es la que de verdad llevaría a una visita de parcela real, y que las notas contextuales aportan (no que sean ruido).

## 14. Posibles motivos para NO implementar la idea

- **Sin persistencia del estado de casillas**, esta v1 es una plantilla reutilizable, no un historial de visitas — si el valor real está en volver a consultar "qué se marcó la última vez", esta versión no lo cubre; sería una extensión razonable (guardar en el `proyecto`, mismo lugar que `sitio`), pero el encargo no la pidió y añadirla ahora dobla el alcance de una pieza que se valoró explícitamente como "barata".
- **Sin exportación a PDF real** (reportlab, como `pdf_report.py`): se usa `window.print()` del navegador, más barato y suficiente para "llevar al terreno", pero con menos control de maquetación que un PDF generado a medida — si Pablo quiere una plantilla con la identidad visual de ArchMuse impresa, esto no lo da.
- **El valor real de este checklist depende de que las notas contextuales sean buenas**, y eso depende de qué tan poblado esté `sitio.datos` para cada proyecto — para proyectos sin Paso 0, el checklist es correcto pero genérico, y "genérico" puede sentirse como poco más que una lista de Google.

---

**Decisión:** Implementado 2026-08-16 — alcance completo (§11, tareas 1-6), verificado en vivo con datos reales de dos proyectos guardados.
