# PRD — Viabilidad económica y exportación a DXF/CAD

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: una nueva pestaña/panel "Viabilidad Económica y Exportación" con (1) un resumen de costes estimados (PEM orientativo = superficie construida × ratio €/m², repercusión de suelo, margen bruto) y (2) un botón "Descargar DXF / CAD" que convierta la geometría 2D de la planta activa (muros, puertas, huecos) a un `.dxf` descargable.

Es capacidad nueva en el sentido estricto de `CLAUDE.md` — ninguna de las dos piezas existe hoy. Antes de proponer el plan, dos hallazgos que cambian el planteamiento de cada una:

- **Viabilidad económica**: la app hoy no tiene ningún ratio de coste por m², ningún valor de repercusión de suelo, ni ningún dato de mercado — el único campo relacionado es un "Presupuesto" de texto libre que el propio arquitecto escribe en la entrevista (`entrevista.js:235`, ej. "300.000 - 400.000 €"), no un cálculo. Cualquier ratio €/m² que se muestre aquí sería, hoy, un número inventado por ArchMuse sin fuente real detrás — exactamente el riesgo que este proyecto ya se ha negado a asumir en otras piezas (checklist de campo, límites urbanísticos de ejemplo, superficie mínima por comunidad autónoma): nunca presentar como dato real algo que no lo es.
- **Exportación a DXF**: el modelo de datos de un proyecto generado (`Room`/`Unit` en `ai_generator.py`, lo que dibuja `plan_svg.py`) son **polígonos de habitación**, no una maqueta CAD con muros con espesor, puertas con simbología de apertura ni huecos de ventana posicionados — ese nivel de detalle no se genera hoy en ningún punto del pipeline. Un DXF que dijera tener "muros, puertas y huecos" estaría inventando geometría que nadie diseñó. Lo que sí se puede exportar con honestidad son los contornos reales de cada estancia (el mismo dato que ya alimenta el SVG), como polilíneas cerradas por capa/nombre — es la escala de fidelidad que el dato de verdad soporta.

Este PRD cubre ambas piezas porque Pablo las pidió como un único panel, pero cada una tiene su propio riesgo y puede aprobarse/implementarse por separado (ver §11).

## 1. Problema que resuelve

Hoy, tras generar o analizar un proyecto, ArchMuse no dice nada sobre si el proyecto es viable económicamente, ni permite sacar la geometría de un proyecto **generado por IA** (sin DXF de origen) a una herramienta CAD externa — solo existe exportación DXF para proyectos que ya partieron de un DXF subido (`descargarDxfRelleno`, que rellena el original, no genera uno nuevo). Un arquitecto que genera un proyecto desde cero con IA no tiene forma de llevárselo a AutoCAD/Revit para seguir trabajando.

## 2. Usuario afectado

El arquitecto (o el promotor que consulta el proyecto con él) que quiere una primera lectura de viabilidad económica sin salir de ArchMuse, y el arquitecto que, tras generar un proyecto con IA, necesita continuar el desarrollo del plano en su CAD habitual.

## 3. Objetivo de negocio

La viabilidad económica conecta con el pilar de "asesor" de `NORTH_STAR_2031.md` (ir más allá de generar/analizar, hacia decidir), pero solo si el dato es honesto — un ratio inventado que luego resulta muy distinto del real es el tipo de fallo de confianza que `DESTROY_ARCHMUSE.md` señala como letal para un producto que se apoya en la credibilidad técnica. La exportación DXF cierra una brecha real de interoperabilidad: hoy un proyecto generado con IA es un callejón sin salida fuera de ArchMuse.

## 4. Objetivo técnico

**Viabilidad económica:**
- Mostrar Superficie Construida Total (dato ya existente, `cuadro_superficies.py`/`evaluator.py`) × un ratio de coste de ejecución material (€/m²) **configurable por el propio arquitecto**, nunca un valor por defecto presentado como de mercado real — hasta que exista una fuente de datos de mercado verificada (ver §9/§14), el ratio lo introduce el usuario y el PEM resultante se etiqueta explícitamente como orientativo/estimado por el propio arquitecto, mismo patrón visual que el badge "Ejemplo" ya usado en el Sandbox (Fase 1, esta sesión).
- Repercusión de suelo y margen bruto: mismo criterio — campos de entrada del arquitecto (precio de venta estimado, coste de suelo), nunca datos de mercado que ArchMuse no tiene.

**Exportación DXF:**
- Botón "Descargar DXF / CAD" en la planta activa que genera un `.dxf` con los contornos reales de cada estancia como polilíneas cerradas, con capa/nombre por estancia — mismo dato que ya usa `plan_svg.py`, servido en un formato distinto.
- Nunca se etiqueta el resultado como "muros, puertas y huecos" si eso no es lo que contiene — el nombre del botón y cualquier texto de ayuda deben describir con precisión lo que de verdad se exporta (ver §6 para el caso con espesor de muro real disponible).

## 5. Casos de uso

1. Arquitecto abre un proyecto generado, va a "Viabilidad Económica", introduce un ratio de coste €/m² propio → ve el PEM orientativo calculado y claramente marcado como estimación suya, no de ArchMuse.
2. El mismo arquitecto introduce precio de venta estimado y coste de suelo → ve margen bruto y repercusión de suelo, igual de honestamente marcados.
3. Arquitecto con un proyecto generado por IA (sin DXF de origen) pulsa "Descargar DXF / CAD" en la planta activa → recibe un `.dxf` con los contornos de las estancias de esa planta, abrible en su CAD.
4. Arquitecto con un proyecto **analizado desde un DXF real** (tiene espesor de muro real en el DXF original) pulsa el mismo botón → aquí sí podría exportarse con más fidelidad (el dato de origen existe), caso distinto al anterior — ver §6.

## 6. Casos límite

- **Proyecto generado por IA vs. proyecto analizado desde DXF real**: fidelidad distinta. El analizado desde DXF SÍ tiene geometría de origen con más detalle (el DXF subido por el propio arquitecto); el generado por IA solo tiene polígonos de habitación. El botón debe comportarse igual en ambos (mismo formato de salida: contornos de estancia), o el generado desde DXF real podría ofrecer el DXF *reconstruido* completo en vez de solo contornos — decisión pendiente de alcance (§11).
- **Ratio de coste no introducido por el arquitecto**: el panel no debe inventar un valor por defecto — se queda vacío/sin calcular hasta que el arquitecto lo rellena, mismo criterio "no disponible, no error" que el resto del producto.
- **Proyecto sin ninguna planta activa clara** (p. ej. vista "Edificio completo" sin vivienda seleccionada): el botón de exportación debe indicar qué planta/vivienda se exportará, o desactivarse si no hay una selección inequívoca.

## 7. Flujo del usuario

**Viabilidad económica:**
1. Arquitecto abre un proyecto (generado o analizado) y entra en la nueva pestaña "Viabilidad Económica y Exportación".
2. Ve la Superficie Construida Total (dato real, ya calculado).
3. Introduce ratio €/m², precio de venta estimado y coste de suelo (todos opcionales, todos suyos).
4. Ve PEM orientativo, repercusión de suelo y margen bruto, recalculados en vivo, marcados como estimación propia.

**Exportación DXF:**
1. Desde la misma pestaña (o desde la vista de planta activa), pulsa "Descargar DXF / CAD".
2. El navegador descarga un `.dxf` con los contornos de las estancias de la planta actualmente activa.

## 8. Criterios de aceptación

1. La Superficie Construida Total mostrada coincide exactamente con la que ya calcula `cuadro_superficies.py`/`evaluator.py` para ese proyecto — mismo número, sin recalcular por separado.
2. Ningún ratio de coste, precio o valor de suelo aparece pre-rellenado como si fuera un dato real de ArchMuse — todos parten vacíos y llevan indicación visual de estimación del propio usuario mientras no exista una fuente de mercado verificada.
3. El `.dxf` descargado se abre sin errores en al menos un visor/editor DXF estándar (verificar con `ezdxf` de lectura, ya dependencia del proyecto, como comprobación mínima) y contiene un polígono cerrado por estancia de la planta activa, con nombre/capa identificable.
4. Ningún texto de la interfaz describe el DXF exportado como "muros, puertas y huecos" salvo que el contenido real lo sea.

## 9. Riesgos

- **Riesgo de credibilidad, no solo técnico**: un ratio €/m² mal calibrado que se perciba como "el número de ArchMuse" en vez de "el número que introdujo el arquitecto" puede dañar la confianza en todo el producto — el diseño visual de esta pestaña tiene que dejarlo inequívoco, no como una nota pequeña.
- **Expectativa desalineada en la exportación DXF**: el encargo original pide "muros, puertas y huecos", y lo que el dato soporta hoy son contornos de estancia. Si se entrega silenciosamente algo más pobre de lo pedido sin explicarlo, es peor que no entregarlo — este PRD asume que la conversación sobre alcance real (§0) ya deja esto claro antes de implementar.
- Compite por tiempo con lo ya priorizado en `REFACTOR_MASTERPLAN.md`.

## 10. Impacto sobre módulos existentes

- **Nuevo** módulo de exportación DXF (`analyzer/dxf_export.py` o similar): función pura que recibe la geometría de una planta (la misma que consume `plan_svg.py`) y produce un documento `ezdxf` con polilíneas cerradas por estancia.
- `app.py`: nuevo endpoint `GET/POST /api/proyectos/<id>/exportar-dxf` (o equivalente para proyectos aún no guardados), reutilizando el patrón ya existente de descarga de archivo (`Content-Disposition: attachment`, mismo criterio que `descargarDxfRelleno`).
- `static/app.js` o el visor de planta correspondiente: nuevo botón "Descargar DXF / CAD", nueva pestaña/panel "Viabilidad Económica y Exportación" (con su propio HTML/CSS, sin modales — mismo criterio del resto del proyecto).
- Ningún cambio en `evaluator.py` ni en el cálculo de Superficie Construida Total — se reutiliza el dato ya calculado, no se recalcula.

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/dxf_export.py`: función pura `exportar_planta_dxf(habitaciones: list) -> ezdxf.Document`, sin I/O, testeable con datos sintéticos.
2. `app.py`: endpoint de descarga, reutilizando el patrón de `descargarDxfRelleno`.
3. UI: botón "Descargar DXF / CAD" en la vista de planta activa.
4. UI: nueva pestaña/panel "Viabilidad Económica y Exportación" — campos de entrada (ratio €/m², precio de venta, coste de suelo), cálculo en vivo, badges de "estimación propia" en cada resultado.
5. Verificación: los 4 criterios de §8, con un proyecto generado por IA y uno analizado desde DXF real.

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/dxf_export.py`.
- Prueba de round-trip: exportar un DXF y volver a leerlo con `ezdxf` para confirmar que las polilíneas cierran y tienen la superficie esperada (comparando con el área ya conocida de cada estancia).
- En vivo: los 4 casos de uso de §5, con un proyecto generado y uno analizado.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que el PEM orientativo, tal como se presenta, no podría confundirse con un dato de mercado real de ArchMuse; y que el DXF exportado se abre correctamente en un CAD externo real.

## 14. Posibles motivos para NO implementar la idea (o para recortar el alcance)

- **Viabilidad económica sin una fuente de ratios de mercado real es, en el mejor de los casos, una calculadora que el arquitecto podría hacer en una hoja de cálculo** — el valor añadido de que viva dentro de ArchMuse es bajo mientras el ratio lo pone el propio usuario. El salto de valor real llegaría con una fuente de datos de mercado verificada (por zona/tipología), que no existe hoy y es un proyecto aparte, más grande. Recomiendo esta versión solo como "calculadora asistida" explícita, no como "estimación de ArchMuse".
- **La exportación DXF, tal como el dato lo permite hoy (contornos de estancia, sin muros/puertas/huecos reales), tiene un valor limitado para un arquitecto que espera continuar el proyecto en CAD** — un contorno de habitación sin espesor de muro ni huecos no ahorra mucho trabajo de redibujado. Si el valor real que se busca es "continuar en CAD de verdad", puede que el proyecto que merezca la pena sea, en su lugar, dotar al generador de un modelo de muros/puertas/huecos real (mucho más grande, toca `ai_generator.py`/`plan_svg.py` a fondo) — y esta exportación de contornos quedaría como una pieza menor dentro de ese proyecto mayor, no como el objetivo en sí.
- Si Pablo confirma que el valor está en tener *algo* exportable ya, aunque sea solo contornos, y *algo* de cálculo de viabilidad aunque el ratio lo ponga el propio usuario, este PRD tal como está es implementable en el alcance descrito.

---

**Decisión:** _pendiente de revisión por Pablo_
