# PRD — Exportación a IFC 4 (BIM)

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: `analyzer/ifc_export.py` + endpoint `/api/exportar-ifc` que convierta la planta a `IfcWall`, `IfcSlab`, `IfcSpace`, `IfcDoor`/`IfcWindow` con propiedades LOD 300 (espesores de muro, alturas, tipología), botón "Descargar Modelo BIM (.IFC)".

Antes de proponer plan: este es el PRD del día con **mayor distancia entre lo pedido y lo que el dato real permite**, y es la tercera vez hoy que un encargo choca con la misma carencia de fondo. Verificado leyendo el código, no de memoria:

- **ArchMuse no tiene espesor de muro en ningún punto del pipeline real.** Tres sitios distintos del código lo documentan explícitamente: `analyzer/dxf_export.py:7` ("No hay muros con espesor, ni puertas..."), `analyzer/cuadro_superficies.py:445` ("ArchMuse mide superficie útil a cara interior de muro; no conoce el espesor..."), `analyzer/evaluator.py:597` ("el espesor de los cerramientos queda fuera [del modelo]"). El único número parecido a un espesor en todo el repositorio es un `0.15` en `analyzer/gltf_exporter.py:196` — un offset puramente cosmético para que el visor 3D dibuje una línea de muro visible, no una medición real de ningún proyecto.
- **ArchMuse no tiene puertas ni ventanas modeladas como geometría.** Ya documentado en `circulation.py:8-16` ("el modelo no tiene datos reales de puertas") y reafirmado hoy en el PRD de checklist CTE (`docs/prd/2026-08-17-checklist-cumplimiento-cte.md` §6): el hueco de paso solo es evaluable cuando existe un hueco real detectado en un DXF de origen, y en proyectos generados por IA no existe en absoluto.
- **`IfcWall`, `IfcSlab` y `IfcDoor`/`IfcWindow` a LOD 300 exigen exactamente los tres datos que no existen**: espesor de muro real, geometría de forjado real (hoy solo hay polígonos de habitación sin espesor de losa), y posición/dimensión real de huecos. Generar estas entidades hoy implicaría **inventar** espesores de muro, materiales y posiciones de puerta/ventana que nadie ha diseñado, y entregarlas dentro de un archivo `.ifc` — un formato que Revit, ArchiCAD y Solibri interpretan como **datos de proyecto reales, no como una estimación**. Un ingeniero que abra ese IFC en Solibri para detección de colisiones, o un aparejador que saque mediciones de muro para presupuesto, estaría trabajando sobre espesores y huecos que ArchMuse se inventó — es el mismo riesgo de credibilidad que este proyecto ya se ha negado a asumir en cada PRD de hoy, pero aquí el daño potencial es mayor: un archivo BIM se usa aguas abajo para decisiones técnicas (estructura, instalaciones, presupuesto), no solo se mira.
- **`IfcSpace` es la única entidad de las cuatro pedidas que hoy se puede generar con datos 100% reales**: los polígonos de habitación, la superficie (útil y construida, ya calculadas con fuentes verificadas) y el uso/tipología de cada estancia existen y son honestos.

Esto no es un "no" al proyecto — es la señal de que el encargo real, si se quiere de verdad LOD 300 con muros/puertas/ventanas, es antes que nada **dotar al pipeline de un modelo de muros con espesor y huecos posicionados** (toca `ai_generator.py`, `parser.py`, `plan_svg.py` a fondo). Este es ya el **tercer PRD en el mismo día** que tropieza con esta misma carencia (el de exportación DXF con muros reales, el de checklist CTE con hueco de paso, y ahora este) — es una señal fuerte de que ese modelo de datos merece ser su propio proyecto prioritario en vez de seguir apareciendo como bloqueo lateral en cada PRD nuevo (ver §14).

## 1. Problema que resuelve

Hoy un proyecto de ArchMuse (generado por IA o analizado desde DXF) no tiene ninguna vía de salida hacia el ecosistema BIM profesional (Revit, ArchiCAD, Solibri) — solo existe exportación DXF de contornos de estancia (PRD 2026-08-17, ya con la misma limitación de fondo).

## 2. Usuario afectado

El arquitecto que necesita continuar el desarrollo del proyecto en un flujo BIM real, o coordinarlo con estructuristas/instaladores que trabajan en Revit/ArchiCAD, o un gestor de proyecto que valida el modelo en Solibri.

## 3. Objetivo de negocio

Interoperabilidad BIM es una casilla que el mercado profesional espera — conecta con `NORTH_STAR_2031.md` en el eje de integrarse en el flujo real del arquitecto. Pero el riesgo de `DESTROY_ARCHMUSE.md` aquí es directo: la primera vez que un arquitecto abra un IFC de ArchMuse en Revit y descubra que los muros tienen un espesor inventado y las puertas están en sitios que nadie diseñó, la conclusión no será "es una versión beta" — será "no me puedo fiar de los datos de ArchMuse", y eso contamina la confianza en el resto del producto, no solo en esta exportación.

## 4. Objetivo técnico (alcance honesto recomendado — ver §14 para el alcance completo pedido)

- `analyzer/ifc_export.py`: función pura que recibe la geometría ya disponible (polígonos de habitación, superficie útil/construida por estancia, uso/tipología, altura de planta si existe) y genera un `IfcSpace` por estancia con esos datos reales, usando `ifcopenshell` (nueva dependencia — ver §9).
- `IfcWall`/`IfcSlab`/`IfcDoor`/`IfcWindow` **no se generan en la v1** salvo que Pablo decida explícitamente asumir espesores/posiciones por defecto **marcados sin ambigüedad como estimación de ArchMuse, no medición real** (mismo patrón que el resto de la app) — ver las dos opciones en §14.
- El archivo `.ifc` resultante debe abrir sin error en al menos un visor IFC estándar (verificación mínima, ver §12) — no se promete compatibilidad certificada con Revit/ArchiCAD/Solibri sin pruebas reales en esas tres herramientas (ver §9).

## 5. Casos de uso

1. Arquitecto con un proyecto generado o analizado pulsa "Descargar Modelo BIM (.IFC)" → recibe un `.ifc` con un `IfcSpace` por estancia, superficie y uso correctos, abrible en un visor IFC.
2. (Si Pablo aprueba la opción B de §14) Arquitecto ve, junto al botón, un aviso explícito de que los muros/huecos del IFC son una aproximación con espesores por defecto configurables, no una medición del proyecto.

## 6. Casos límite

- **Proyecto sin altura de planta definida**: `IfcSpace` no puede llevar una altura real — usar la misma que ya usa el visor 3D/gltf si existe un valor consistente en el pipeline, o dejar la propiedad vacía en vez de inventar 2.50 m u otro valor no verificado.
- **Estancia sin uso/tipología clara**: mismo criterio que el resto del proyecto — `IfcSpace.LongName`/`ObjectType` sin rellenar en vez de una tipología adivinada.
- **Proyecto analizado desde DXF real con espesor de muro SÍ disponible en el DXF de origen** (si `parser.py` en algún caso captura esa capa): caso distinto y potencialmente más honesto para `IfcWall` — requiere confirmar primero si `parser.py` realmente extrae espesor en algún escenario o si esto también es cosmético (ver §9, tarea de investigación previa).

## 7. Flujo del usuario

1. Arquitecto abre un proyecto con estancias resueltas.
2. Pulsa "Descargar Modelo BIM (.IFC)".
3. El navegador descarga un `.ifc` con los `IfcSpace` reales del proyecto (y, si se aprueba §14-B, muros/huecos marcados como estimación).

## 8. Criterios de aceptación

1. Cada `IfcSpace` del `.ifc` tiene la misma superficie (útil/construida) que ya muestra el resto de la app para esa estancia — mismo dato, sin recalcular.
2. El `.ifc` se abre sin error en un visor IFC de verificación (`ifcopenshell` de lectura, o un visor gratuito como BIMcollab Zoom) — comprobación mínima de round-trip.
3. Ninguna propiedad del IFC se presenta como medición real cuando es un valor por defecto no verificado — si se implementa §14-B, cada `IfcWall`/`IfcDoor` lleva una `Pset` o comentario que lo marca como estimación de ArchMuse.
4. El nombre del botón y cualquier texto de ayuda describen con precisión qué contiene el IFC — nunca "LOD 300 completo" si el contenido real es solo `IfcSpace`.

## 9. Riesgos

- **Riesgo de credibilidad profesional, el más alto de los PRD de hoy**: un BIM con datos inventados usado aguas abajo por otro profesional (estructurista, instalador, medición de presupuesto) puede causar daño real fuera de ArchMuse, no solo una mala impresión — es un nivel de riesgo distinto a un ratio €/m² que el propio usuario introdujo y sabe que es suyo.
- **`ifcopenshell` es una dependencia nueva y pesada** (extensión nativa, no pure-Python) — instalar y mantenerla en Windows/CI no es trivial; conviene confirmar que el entorno de despliegue (Railway, según memoria del proyecto) la soporta antes de comprometerse a la librería, no después.
- **"Compatible con Revit, ArchiCAD y Solibri" es una afirmación que solo se puede hacer tras probarlo en las tres herramientas reales** — ArchMuse no tiene hoy acceso a licencias de esas tres para verificarlo; el criterio de aceptación de §8 se limita a un visor IFC de verificación, no a las tres herramientas nombradas en el encargo, salvo que Pablo pueda facilitar acceso a alguna para probar.
- Compite por tiempo con `REFACTOR_MASTERPLAN.md` y con el resto de PRDs en cola hoy (Viabilidad Financiera, checklist CTE) — y, más que ninguno de ellos, revela la misma carencia de fondo (sin muros/huecos reales) que esos dos PRDs también señalan.

## 10. Impacto sobre módulos existentes

- **Nuevo** `analyzer/ifc_export.py`, nueva dependencia `ifcopenshell` en `requirements.txt`.
- `app.py`: nuevo endpoint `GET/POST /api/exportar-ifc`, mismo patrón de descarga que `descargarDxfRelleno`/el nuevo endpoint DXF.
- `static/`: nuevo botón "Descargar Modelo BIM (.IFC)", junto al de "Descargar DXF / CAD" ya existente en la pestaña de Viabilidad Económica y Exportación (mismo sitio natural, no un panel nuevo).
- Ningún cambio en `evaluator.py`/`cuadro_superficies.py` — se reutilizan superficies y usos ya calculados.

## 11. Plan de implementación dividido en pequeñas tareas (alcance §4, IfcSpace-only)

1. Confirmar que `ifcopenshell` instala y funciona en el entorno real del proyecto (Windows local + Railway) antes de escribir código de producto — spike de 1 tarea, no asumido.
2. `analyzer/ifc_export.py`: función pura `exportar_proyecto_ifc(unit) -> ifcopenshell.file`, un `IfcSpace` por estancia con superficie y uso reales.
3. `app.py`: endpoint de descarga.
4. UI: botón "Descargar Modelo BIM (.IFC)".
5. Verificación: round-trip de lectura con `ifcopenshell`, y apertura en un visor IFC gratuito.
6. (Solo si Pablo aprueba §14-B) Tareas adicionales para `IfcWall`/`IfcSlab`/`IfcDoor`/`IfcWindow` con espesores por defecto marcados como estimación — a detallar después de esa decisión, no antes.

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/ifc_export.py`.
- Prueba de round-trip: exportar y releer con `ifcopenshell`, comprobar que cada `IfcSpace` tiene la superficie esperada.
- En vivo: descargar el `.ifc` de un proyecto real y abrirlo en un visor IFC gratuito (p. ej. BIMcollab Zoom o el propio `ifcopenshell` con geometría), confirmar que no da error de apertura.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que el `.ifc` exportado no podría malinterpretarse como un modelo BIM completo (muros/huecos reales) cuando en realidad solo contiene espacios, y que se abre sin error en al menos un visor externo real.

## 14. Posibles motivos para NO implementar la idea (o para recortar el alcance)

Dos caminos posibles, y recomiendo que Pablo elija explícitamente uno antes de que se escriba código:

- **(A) Alcance honesto — recomendado**: implementar solo `IfcSpace` (superficie + uso reales), dejar `IfcWall`/`IfcSlab`/`IfcDoor`/`IfcWindow` fuera hasta que exista un modelo real de muros/huecos en el pipeline (el proyecto de fondo que tres PRDs de hoy ya han señalado como bloqueo compartido). El botón se llamaría con precisión ("Descargar Espacios BIM (.IFC)" o similar), no "Modelo BIM" completo, para no prometer LOD 300. Es un IFC honesto pero de valor limitado — probablemente insuficiente para lo que Pablo espera de "compatible con Revit/ArchiCAD/Solibri" en el sentido profesional habitual (coordinación con estructura/instalaciones necesita muros reales).
- **(B) Alcance con muros/huecos por defecto, explícitamente marcados como estimación**: generar `IfcWall`/`IfcDoor`/`IfcWindow` con espesor de muro por defecto (p. ej. 15 cm exterior, 10 cm interior — parámetros configurables por el usuario, igual que el ratio €/m² de Viabilidad Económica) y puertas centradas en cada adyacencia con pieza de circulación (aproximación geométrica, no un hueco real). Cada entidad lleva una propiedad IFC (`Pset_ArchMuseEstimacion` o similar) que dice explícitamente "espesor/posición estimados por ArchMuse, no medidos". Da un modelo más útil para una primera coordinación visual, pero con más riesgo de que alguien lo use aguas abajo sin leer el aviso — el riesgo de `DESTROY_ARCHMUSE.md` señalado en §9 se mitiga pero no desaparece.
- **La alternativa de fondo, si Pablo quiere el "sí" completo al encargo original**: priorizar antes un proyecto que dote a `ai_generator.py`/`parser.py`/`plan_svg.py` de un modelo real de muros con espesor y huecos posicionados — más grande, pero es lo que de verdad destraba este PRD, el de DXF con muros reales, y el de hueco de paso del checklist CTE **a la vez**, en vez de parchear cada uno con estimaciones por separado.
- Si Pablo confirma la opción A o B, y confirma que el spike de `ifcopenshell` en el entorno real (tarea 1 de §11) no bloquea, este PRD es implementable en el alcance elegido.

---

**Decisión:** **Aprobado (2026-08-17) — opción A de §14**. Solo `IfcSpace` (superficie + uso reales), sin `IfcWall`/`IfcSlab`/`IfcDoor`/`IfcWindow` ficticios. La acción se llama explícitamente **"Exportar Espacios BIM (.IFC)"**, no "Modelo BIM", para no prometer LOD 300.
