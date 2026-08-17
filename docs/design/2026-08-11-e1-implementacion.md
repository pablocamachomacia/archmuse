# E1 — Registro de la implementación real del modelo arquitectónico común

**Fecha:** 2026-08-11 · **Tipo:** registro de implementación · **Estado:** ejecutado, sin commit
**Plan:** [`docs/prd/2026-08-11-e0-modelo-arquitectonico.md`](../prd/2026-08-11-e0-modelo-arquitectonico.md) § Plan de E1
**Diseño:** [`2026-08-11-modelo-arquitectonico-comun.md`](2026-08-11-modelo-arquitectonico-comun.md) · [`../brain/KNOWLEDGE_GRAPH.md`](../brain/KNOWLEDGE_GRAPH.md)

Este documento registra **qué se construyó de verdad** y, sobre todo, **en qué se desvió de lo planeado y por qué**.
No repite el diseño ni el contrato: para eso están los dos documentos de arriba. Lo único que añade son los hechos
medidos y las cuatro desviaciones.

---

## 1. Qué existe ahora

```
modelo/                     capa nueva, aislada, 11 modulos
├── identidad.py            C1  instance_id determinista + concept_id opaco
├── atributo.py             C5  vocabulario de hechos.py, estado x origen
├── geometria.py            C4  AlmacenGeometria: geom_id -> shapely, en metros
├── nodos.py                C2  Proyecto/Edificio/Planta/Unidad/Espacio + presencia de 11 tipos
├── aristas.py              C3  es_contiguo_a / conecta_con + Criterio
├── grafo.py                    version sellada + API de lectura + VistaUnidad
├── invariantes.py          C6  I1..I8, comprobados al sellar
├── serializacion.py        C7  JSON determinista + round-trip + sellado sha256
├── constructor.py              unica aduana con parser/evaluator/adyacencia
├── compat.py                   unica salida hacia evaluator.Unit
└── __init__.py
```

Sobre `ejemplo.dxf`: **34 espacios, 6 unidades, 1 planta, 1 edificio, 45 aristas de cada tipo**, sellado estable
entre procesos. Cinco tipos de nodo materializados; los otros seis existen sólo como presencia declarada.

**Único fichero de producción modificado:** `analyzer/circulation.py` (+32 −2). `_build_adjacency_graph` deja de
llamar a `adyacencia.construir_grafo` y pide la topología al modelo. Nada más del repositorio cambia.

## 2. Neutralidad — lo que se midió, no lo que se supone

| Comprobación | Resultado |
|---|---|
| Agrupación: adaptador vs `group_rooms_by_unit_label` | mismas 6 viviendas, mismo orden, misma composición, mismas áreas al nanómetro² |
| Hechos de CAP-1…CAP-5 alimentados por el modelo | **37 hechos idénticos**, uno a uno (valor, estado, confianza, códigos de motivo) |
| Grafo de adyacencia vs `analyzer/adyacencia.py` | mismas aristas, mismos pesos y **el mismo orden de vecinos** (90 medio-aristas) |
| Circulación | **12 comprobaciones idénticas** en las 6 viviendas |
| G9 ↔ G3 | **45 de 45** aristas coinciden, con sus separaciones y distancias |
| Suite completa | 56 ficheros, 55 OK, 1 FALLO — el conocido de `test_scoring_coherencia.py` |

El orden de vecinos importa y por eso se comprueba aparte: decide qué camino gana cuando dos empatan. Sin esa
condición, la migración habría medido el desempate en vez de la arquitectura.

## 3. Desviaciones

### D1 — `derivados` sale del formato de serialización

- **Decisión original (C7):** el ejemplo de JSON del PRD incluía un bloque `derivados` (área, perímetro,
  centroide…) dentro de cada espacio.
- **Problema:** rompía la regla C7.4, round-trip sin pérdida. Los derivados se calculan de la geometría exacta al
  volcar; al cargar, la geometría vuelve redondeada al milímetro, así que el segundo volcado daba
  `area_m2: 12.724` donde el primero decía `12.725`. Medido: **357 líneas de diferencia, todas en `derivados`**;
  ni un nodo, arista, identidad o atributo cambiaba.
- **Solución:** `derivados` fuera del formato. El JSON persiste **fuentes** (los puntos del contorno); quien
  necesite área la pide al API. **G9 sí los congela**, porque eso es trabajo del golden, no del formato.
- **Impacto:** JSON algo menos legible de un vistazo; round-trip exacto y sellado estable. Ningún consumidor
  pierde nada — no había ninguno.
- **Compatible porque** es literalmente el principio P7 del diseño: «si un dato puede derivarse del modelo, no se
  persiste como dato». El `cargar()` ya lo decía en su docstring; el formato no lo cumplía.

### D2 — La diferencia de VT6/2 **no se produce** (pasos E1.14 y E1.15)

- **Decisión original:** E1.14 documentaba la desaparición del falso positivo de VT6/2 («Baño: acceso directo
  desde Salón/cocina, sin antesala», apoyado en 0,000 m de tramo enfrentado) y **pedía tu aprobación explícita**;
  E1.15 recapturaba G4 con esa diferencia.
- **Problema:** la diferencia no ocurre. El falso positivo desaparece con el **criterio estricto** (tramo mínimo
  0,60 m), y la decisión 3 que cerraste dice que E1 conserva el criterio actual y mide `tramo_m` sin usarlo como
  filtro. Con el criterio de hoy, el modelo ve exactamente los mismos 45 pares que `adyacencia.py`.
- **Solución:** no hay nada que aprobar ni que recapturar. G4 sigue congelado tal cual, con su nota de defecto
  conocido intacta. El falso positivo **sigue en producción**, y sigue siendo el argumento a favor de cerrar el
  umbral cuando lleguen los proyectos reales.
- **Impacto:** E1 resulta **más neutro** de lo que el plan preveía: cero diferencias de comportamiento, ninguna.
- **Compatible porque** el plan pedía neutralidad demostrable y la obtiene sin excepciones. La predicción del PRD
  se escribió antes de cerrar la decisión 3; las dos no eran compatibles y ha ganado la decisión.

### D3 — `profundidad_maxima` no se implementa; en su lugar, `lado_mayor_m` y `lado_menor_m`

- **Decisión original:** `KNOWLEDGE_GRAPH.md` §0.2 lista «profundidad máxima desde el borde» entre los derivados
  admitidos.
- **Problema:** no pasa su propio filtro. La profundidad que le importa a la iluminación natural es la distancia
  **desde la fachada**, y saber qué lado del polígono es fachada exige mirar otros nodos — luego no es función
  pura de la geometría del propio nodo.
- **Solución:** se publican `lado_mayor_m` y `lado_menor_m` del rectángulo envolvente mínimo: puros, estables y
  suficientes para los mismos usos.
- **Impacto:** ninguno hoy (no había consumidores). Cuando exista `Hueco`, la profundidad desde fachada será un
  **hecho derivado** del dominio, no un atributo del nodo.
- **Compatible porque** aplica el criterio de §0.2 con más rigor que la propia lista de §0.2.

### D4 — La frontera del constructor incluye `analyzer.adyacencia`

- **Decisión original (E1.1):** `parser`/`evaluator` sólo en `constructor.py` y `compat.py`.
- **Problema:** el umbral de contigüidad vive hoy en `adyacencia.WALL_GAP_TOLERANCE_M`. Si el modelo tuviera su
  propia copia habría **dos definiciones del mismo número**, que es exactamente lo que este modelo existe para
  eliminar (principio P5).
- **Solución:** `modelo/aristas.Criterio.tolerancia_muro_m` nace a `None` y el constructor la rellena leyendo
  `adyacencia.WALL_GAP_TOLERANCE_M` en cada construcción. La frontera se amplía a esos tres módulos, sólo en la
  aduana, y el test la vigila.
- **Impacto:** medible y bueno — la mutación K1 del canario (bajar el umbral a 0,25 m) rompe **también G9**, lo
  que demuestra que el modelo lee el número y no lo ha copiado.
- **Compatible porque** la dependencia va del modelo al sustrato en el único módulo cuyo trabajo es hablar con el
  sustrato, y es temporal: en E2 la tolerancia pasa a ser un dato del proyecto persistido.

**Lo que NO se desvió:** los cinco nodos, las dos aristas, los ocho invariantes, la identidad en dos niveles, la
geometría por referencia, `Atributo` sobre `hechos.py` sin tocarlo, y los quince pasos en su orden.

## 4. Qué vigila ahora la red de seguridad

**G9 (nuevo)** congela el modelo serializado entero, sus derivados y la equivalencia con G3. Se registra en
`tests/golden.py` **antes** de G8, porque G8 sella el manifiesto de todos los demás.

Matriz del canario ampliada, **medida**:

| Mutación | Rompe |
|---|---|
| K1 tolerancia 0,5 → 0,25 | G3, G4, **G9** |
| K2 agrupación por proximidad | G2, G3, G4, G5, G6, **G9** |
| K3 escala ×10 | G1, G2, G3, G4, G5, G6, G7, **G9** |
| K4 «Terraza» → ocupación nula | G5, G6 — **G9 no, y es correcto** |

La última fila es la más informativa: el modelo **no** calcula superficie útil, porque decidir qué recintos entran
en la suma es una regla del dominio y no un dato del proyecto (`KNOWLEDGE_GRAPH.md` §7). Que G9 sea insensible a
K4 es la prueba de que la frontera «el modelo describe, el motor concluye» se sostiene en el código y no sólo en
el documento.

## 5. Lo que E1 deja pendiente, dicho por su nombre

- **Emparejamiento entre versiones** (`identidad.emparejar`): lanza `NotImplementedError` citando E2. Sin él,
  cada lectura asigna `concept_id` nuevos y no hay histórico.
- **Persistencia** (E2): el modelo se construye y se tira. `storage.py` sigue guardando el informe, no el
  proyecto. Es el desbloqueo principal y sigue pendiente.
- **Muro, Hueco, Parcela, Pilar, Instalación, Zona común:** declarados en el mapa de presencia, sin clase.
- **El umbral de contigüidad:** abierto. `tramo_m` se mide y se guarda en las 45 aristas, sin filtrar.
- **Los otros consumidores:** `evaluator.py`, `plan_svg.py`, `spatial_quality.py` y `api_serializer.py` siguen
  intactos y siguen teniendo su propio criterio de agrupación o adyacencia. E1 migró uno de cinco.
- **Límite de la persistencia futura:** un modelo cargado desde JSON tiene precisión de milímetro; uno construido
  desde el DXF conserva la del origen. Recalcular topología sobre el cargado podría mover una arista cuya
  separación estuviera a menos de 1 mm del umbral. Sobre `ejemplo.dxf` no ocurre: el par más próximo al umbral
  está a 120 mm.

---

**Estado:** implementado y verificado, sin commit. `git diff` sobre producción: un solo fichero,
`analyzer/circulation.py`.
