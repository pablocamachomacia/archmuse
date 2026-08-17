# PRD — Exportación glTF y visor georreferenciado (Mapbox)

**Estado:** Borrador, en cola detrás de `2026-08-15-analisis-de-sitio.md` · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Dos correcciones antes de diseñar nada

1. **Depende de `sitio_data`** (`docs/prd/2026-08-15-analisis-de-sitio.md`, sin construir): sin coordenadas y geometría real de la parcela no hay nada que georreferenciar. Cola confirmada por Pablo (2026-08-15): primero verificador de pliegos, luego sitio.py, luego esto.
2. **"La geometría 3D existente" no existe en el servidor.** Comprobado hoy: la extrusión de habitaciones a volúmenes y el apilado de plantas vive entera en `static/viewer-edificio.js`, en el navegador, con three.js — no hay ningún módulo Python que produzca una malla. Un exportador glTF en `analyzer/exportar_gltf.py` no reutiliza nada existente: reimplementa en Python, con `pygltflib`/`trimesh` (ninguno de los dos está en `requirements.txt` hoy), la misma lógica de extrusión que ya vive en JS — con el riesgo real de que las dos implementaciones diverjan con el tiempo si algo cambia en una y no en la otra.

## 1. Problema que resuelve

El visor 3D actual (three.js) muestra el edificio aislado, sin su entorno real — ni el solar real, ni los colindantes reales. Un visor georreferenciado permite ver el proyecto en su emplazamiento de verdad. Encargo directo de Pablo (2026-08-15), explícitamente dividido en dos partes por él mismo (modelo en el mapa primero, sombras solares después).

## 2. Usuario afectado

El mismo arquitecto de los PRDs de sitio/solar, en el momento de presentar o revisar un proyecto en su contexto real — más una audiencia nueva potencial: quien revisa el proyecto sin ser arquitecto (cliente, jurado de concurso), para quien "verlo en el mapa real" comunica mejor que un modelo aislado.

## 3. Objetivo de negocio

Pieza de comunicación/venta más que de análisis — `MOAT_ANALYSIS.md` línea 69 ya señala el visor 3D como una funcionalidad "compleja sin foso real" si no se conecta a algo que sí lo tenga; conectarlo a datos reales de sitio (una vez exista) es la diferencia entre "bonito" y "defendible". Vale la pena leer esa sección antes de aprobar, no solo asumir que más visualización es mejor.

## 4. Objetivo técnico

- Exportar la geometría del proyecto a `.glb` de forma determinista (sin IA), reimplementando en Python la extrusión que hoy solo existe en JS — mismo resultado visual, segunda implementación.
- Posicionar el modelo en coordenadas reales usando `sitio_data` (cuando exista).
- Visor Mapbox con el modelo, colindantes de OSM Buildings, controles básicos — sin sombras solares en esta primera parte (división explícita de Pablo).

## 5. Casos de uso

1. Proyecto con sitio analizado: "Ver en mapa" muestra el modelo real sobre la parcela real, con colindantes.
2. Proyecto sin sitio analizado: el botón "Ver en mapa" no aparece (regla ya explícita del encargo, punto 1 de la Parte 2) — nunca un mapa sin coordenadas reales.

## 6. Casos límite

- **`MAPBOX_TOKEN` no configurado**: el botón "Ver en mapa" no debería ni aparecer, o debe fallar con un mensaje claro — nunca una pantalla en blanco o un error de consola sin explicación.
- **Divergencia entre el modelo three.js y el `.glb` exportado**: si la lógica de extrusión de Python y la de JS se desincronizan (un cambio en una sin el mismo cambio en la otra), el modelo del mapa no coincidiría con el modelo del visor normal — riesgo real de este diseño, no un caso límite raro (ver Riesgos).
- **Colindantes de OSM Buildings sin altura**: mismo caso ya documentado en el PRD de sitio — se muestran sin altura conocida (Mapbox/threebox tiene su propio comportamiento por defecto ahí, a decidir en implementación), nunca con una altura inventada.

## 7. Flujo del usuario

1. (Depende de sitio.py) El proyecto tiene `sitio_data` con coordenadas.
2. "Ver en mapa" en la vista de proyecto.
3. Mapbox carga con el `.glb` posicionado en la parcela real, colindantes de OSM Buildings activados, controles de rotar/zoom/satélite-mapa.

## 8. Criterios de aceptación

- El `.glb` exportado, cargado en cualquier visor glTF estándar, muestra la misma forma que el visor three.js para el mismo proyecto (mismas plantas, mismas alturas).
- Sin `sitio_data`, no hay botón "Ver en mapa" — nunca un mapa con una posición supuesta.
- Sin `MAPBOX_TOKEN`, error claro, no una pantalla rota.

## 9. Riesgos

- **Segunda implementación de la misma geometría es el riesgo estructural de este PRD** — dos lugares (Python, JS) que tienen que producir el mismo resultado, sin ningún mecanismo hoy que lo garantice o lo avise si divergen. Vale la pena considerar, en implementación, un test dorado que compare ambas salidas para el mismo proyecto, no solo confiar en que el código se mantenga sincronizado a mano.
- **Mapbox GL JS no es gratuito sin límite** — tiene un nivel gratuito y factura por uso más allá de él; es una dependencia de coste nueva y distinta a los tokens de Claude, con su propia cuenta y facturación que gestionar. Encaja con la misma pregunta que abrió la sesión de hoy ("que no se me coma tanto de uso") pero en un proveedor distinto — vale la pena decidir esto con los ojos abiertos, no asumirlo gratis por ser "solo un mapa".
- **Segunda dependencia de CDN sin vendorizar** (Mapbox GL JS + threebox, además del three.js ya pendiente de vendorizar — tarea #20 de `REFACTOR_MASTERPLAN.md`, todavía abierta según la auditoría de esta mañana): este PRD duplicaría esa misma deuda en vez de resolverla.
- **`pygltflib`/`trimesh` son dependencias nuevas** — ninguna está en `requirements.txt` hoy; conviene decidir cuál antes de implementar (trimesh es más pesado pero más completo; pygltflib es más ligero y de más bajo nivel).
- **Bloqueado por `sitio.py`** — no se puede secuenciar en tareas concretas todavía; se deja así hasta que exista esa base.

## 10. Impacto sobre módulos existentes

- **`analyzer/exportar_gltf.py`** (nuevo): reimplementa la extrusión de `viewer-edificio.js` en Python.
- **`app.py`**: `GET /api/proyectos/<id>/exportar-gltf`.
- **`static/`**: nuevo visor Mapbox (archivo JS nuevo, mismo patrón de módulo aislado que `viewer-*.js`), botón "Ver en mapa" condicionado a `sitio_data`.
- **Variable de entorno nueva** `MAPBOX_TOKEN` — primera vez que ArchMuse gestiona un secreto de un proveedor que no es Anthropic; conviene el mismo cuidado (nunca en el repo, documentado en un `.env.example` si no existe ya).
- **No toca** `viewer-edificio.js` — la implementación Python es independiente, con el riesgo de divergencia ya señalado.

## 11. Plan de implementación dividido en pequeñas tareas

*(Sin secuenciar en detalle todavía — depende de `sitio.py`. Esbozo de alto nivel para cuando llegue el momento):* extrusión Python (reimplementación deliberada, con test dorado contra la salida de JS) → exportación `.glb` → endpoint → integración Mapbox+threebox → OSM Buildings colindantes → controles básicos.

## 12. Plan de pruebas

- Test dorado comparando la geometría Python vs. una captura conocida del three.js para el mismo proyecto (mitiga el riesgo de divergencia de §9).
- Test de que un `.glb` exportado es válido (parseable por un lector glTF estándar).

## 13. Métricas para medir el éxito

- Nº de veces que se usa "Ver en mapa" por proyecto con sitio analizado.
- Coste real de Mapbox tras el lanzamiento, comparado contra el nivel gratuito — primera medición real de si esta pieza tiene un coste operativo a vigilar.

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **Depende enteramente de un PRD sin construir** — no hay nada que hacer con este hoy más allá de dejarlo escrito.
- **Es la pieza más "demostrativa" y menos "analítica" de toda la cola de hoy** — a diferencia del verificador o el motor de estilos, no ayuda a decidir si un proyecto es bueno o cumple algo; es comunicación visual. Vale la pena confirmar que compite en prioridad con piezas que sí mueven la aguja del producto (verificador, estilos) antes de dedicarle tiempo cuando llegue su turno.
- **Alternativa más barata cuando llegue el momento**: validar primero solo la Parte 1 (exportación `.glb`, sin Mapbox) contra el visor three.js existente — si la reimplementación en Python diverge de forma difícil de mantener, mejor saberlo antes de construir el visor Mapbox encima.

---

**Decisión:** _pendiente — en cola detrás de sitio.py, por decisión de Pablo (2026-08-15)_
