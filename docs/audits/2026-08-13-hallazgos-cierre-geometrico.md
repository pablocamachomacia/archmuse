# 2026-08-13 — Hallazgos de la corrección de cierre geométrico

**Fecha:** 2026-08-13 · **Código:** `analyzer/parser.py::_esta_cerrada` (Fase 0, ver `tests/test_cierre_recuperado.py`)
**Datos:** `ejemplo.dxf` (plano de referencia), `V5.dxf`, `v2s.dxf` (proyectos reales adicionales)
**Método:** auditoría de solo lectura (parche de `_esta_cerrada` en memoria, sin tocar disco) + medición directa contra el pipeline real, seguida de la recongelación de goldens/fixtures cuyo cambio deriva exclusivamente de esta corrección.
**Restricción:** este documento **no implementa ninguna solución** para los dos hallazgos que describe. Los deja documentados como tareas independientes, fuera del alcance de la corrección de cierre geométrico.

---

## 0. Contexto

`_esta_cerrada()` reconocía una polilínea como cerrada solo por su flag DXF `closed`. Varias polilíneas reales tenían ese flag en `False` pese a tener su primer y último vértice geométricamente coincidentes (o casi) — un error de dibujo, no una polilínea abierta de verdad. La corrección añade una segunda comprobación geométrica (`_extremos_coinciden`, tolerancia relativa a la caja envolvente) y registra cada recuperación con `logging.WARNING`, nunca en silencio.

Efecto medido sobre `ejemplo.dxf`: 34 → 40 recintos (8 nuevos, 2 contornos duplicados descartados — ver `tests/test_ingesta_regresion.py` y los goldens `G1`…`G9`). Detalle completo de la auditoría de los tres proyectos reales: sesión de esta misma fecha, no repetido aquí.

Al recongelar los goldens y fixtures afectados por este cambio (34→40 recintos), aparecieron dos hallazgos **independientes** de la corrección de cierre en sí — ninguno de los dos está causado por `_esta_cerrada()`, los dos se hicieron visibles porque, por primera vez, se lee geometría que antes se descartaba entera.

---

## 1. Resumen

| # | Hallazgo | Causado por esta corrección? | Estado |
|---|---|---|---|
| **H1** | `modelo/serializacion.py`: el round-trip JSON pierde un vértice en polígonos con un vértice de cierre explícitamente duplicado, y `storage.obtener_modelo()` devuelve `None` en vez del grafo persistido | Expuesto por esta corrección (los recintos recuperados son los primeros en tener esa forma), no causado por ella | **Sin arreglar, documentado aquí** |
| **H2** | `ejemplo.dxf`, VT6/2: el "Dormitorio 2" recuperado es geométricamente inválido (autointersección), y dos "Terraza" de la misma vivienda ya se solapaban entre sí antes de esta corrección | Pre-existente en el DXF de origen, sin relación con `_esta_cerrada()` | **Sin arreglar, es el comportamiento correcto del sistema (`GEOMETRY_INVALID`/`SOLAPE_NO_RESUELTO` ya existían para esto)** |

---

## 2. H1 — Round-trip de `modelo/serializacion.py` pierde un vértice

**Síntoma:** `storage.obtener_modelo(pid)` devuelve `None` para un proyecto que sí se guardó correctamente. `tests/test_e2_persistencia.py` y `tests/test_e2_construccion_unica.py` fallan (dejados en rojo a propósito, no tocados en esta tarea).

**Causa exacta, verificada byte a byte:** tres de los ocho recintos recuperados por `_esta_cerrada()` en `ejemplo.dxf` tienen, en su lista cruda de vértices (`_polyline_points`), el vértice de cierre repetido explícitamente — es justo lo que permite reconocerlos como cerrados pese al flag `closed=False`. Al volcar y recargar el grafo (`modelo/serializacion.py::volcar`/`cargar`), el redondeo a milímetro colapsa ese vértice duplicado (`geometrias.g-0027.puntos`: 11→10; `g-0029`: 19→18; `g-0034`: 12→11). El conjunto de aristas no cambia, pero el JSON recargado ya no es idéntico byte a byte al original, así que `sellado_de(grafo_recargado) != grafo.sellado` y `verificar_sellado()` (I8) rechaza el modelo.

**Por qué no es un bug de `_esta_cerrada()`:** la corrección solo decide si una entidad se trata como cerrada; no toca, añade ni quita ningún vértice de la lista que devuelve `_polyline_points`. El vértice duplicado ya estaba en el DXF de origen — es, de hecho, la señal que hace que el hueco sea cero o casi cero. Un recinto con `closed=True` de verdad nunca trae ese duplicado (ezdxf no lo añade cuando el flag ya está bien puesto), así que este patrón es exclusivo de los recintos recuperados.

**Impacto real, acotado:** no afecta a ninguna superficie, habitación o campo del JSON que ve el arquitecto — todo eso pasa por `plano.rooms` sin pasar por `modelo/serializacion.py`. Solo afecta a la reconstrucción persistida del modelo arquitectónico común (E2), que `app.py` ya trata como *best-effort* (`grafo = None` si algo falla; el análisis sigue devolviendo el mismo resultado, comentario explícito en `app.py` junto a `modelo_constructor.construir`).

**Posibles direcciones para cuando se aborde (sin decidir aquí):**
- Deduplicar el vértice de cierre explícito en `_polyline_points` (o en el punto de construcción del `Polygon`), para que un recinto recuperado tenga la misma forma de lista de puntos que uno con `closed=True` de verdad.
- O relajar `verificar_sellado()`/`sellado_de()` para que compare geometría redondeada de origen, no la lista cruda de puntos.

---

## 3. H2 — VT6/2 tiene dos defectos de geometría propios, sin relación con el cierre

**Síntoma:** VT6/2 sigue `UNKNOWN` en `superficie_util_db_si`/`ocupacion` tras la corrección (antes también lo estaba, pero por otra causa: el contorno duplicado de "Salón/cocina", ya resuelto). `tests/test_superficie_util_db_si.py`, `tests/test_sectorizacion.py` y `tests/test_analizar_planta.py` ya reflejan este estado y pasan en verde.

**Causa 1 — "Dormitorio 2" autointersecante.** El polígono recuperado de "Dormitorio 2" en VT6/2 tiene, en un punto muy cercano a su vértice de cierre, un tercer vértice a solo ~0,00008 unidades de distancia — una especie de "pico" degenerado que Shapely reporta como autointersección (`Polygon.is_valid == False`, `explain_validity`: `Self-intersection`). Es un defecto real del dibujo original (probablemente un doble clic o un ajuste de snap accidental cerca de esa esquina), no algo que `_esta_cerrada()` introduzca: la corrección solo mira el primer y el último vértice de la lista, nunca los intermedios. El sistema ya tenía la salvaguarda correcta para esto (`superficie_util._revisar`, motivo `GEOMETRY_INVALID`) — simplemente nunca se había ejercido porque el recinto entero era invisible antes.

**Causa 2 — dos "Terraza" de VT6/2 ya se solapaban entre sí.** `_solapes()` mide 2 pares de Terrazas solapadas (4,32 m² y 4,15 m²) dentro de VT6/2, con geometría que **no cambia con esta corrección** (esas 4 entidades ya tenían `closed=True` y se leían igual antes). Antes de esta corrección, este solape ya contribuía a que VT6/2 fuera `UNKNOWN` — solo que el motivo dominante visible era el contorno duplicado de "Salón/cocina" (58,58 m²), que enmascaraba el resto.

**Conclusión:** VT6/2 tiene, y tenía, más de un problema de geometría. Esta corrección resuelve uno (el contorno duplicado del salón, compartido con el caso ya documentado de VT5/1) y dejó visibles, por primera vez, los otros dos — que el sistema ya sabe declarar correctamente como `UNKNOWN` con motivo, sin inventar ninguna cifra. No se propone ninguna solución aquí: arreglar la geometría de origen (o decidir cómo tratar una autointersección tan pequeña) es una tarea aparte, sobre un DXF real de un cliente, no sobre código de ArchMuse.

---

## 4. Qué se tocó y qué no en esta tarea

**Se recongelaron** (verificado que cada diferencia deriva exclusivamente de los 8 recintos nuevos + 2 contornos duplicados descartados en `ejemplo.dxf`):
`tests/fixtures/golden/G1_plano.json` … `G9_modelo.json`, `tests/fixtures/ejemplo-ingesta-referencia.json`, y las constantes/diccionarios hardcodeados de `tests/test_e3_geometria_proporciones.py`, `tests/test_e3_paridad_clasificacion.py`, `tests/test_acoustic_adjacency.py`, `tests/test_analizar_planta.py`, `tests/test_sectorizacion.py`, `tests/test_ocupacion.py`, `tests/test_uso_previsto.py`, `tests/test_superficie_equivalencia.py`, `tests/test_superficie_util_db_si.py`.

**No se tocó:** `modelo/serializacion.py`, `modelo/geometria.py`, ninguna geometría de `ejemplo.dxf`, ni `tests/test_e2_persistencia.py`/`tests/test_e2_construccion_unica.py` (siguen en rojo, a propósito, hasta que H1 se aborde como tarea propia).
