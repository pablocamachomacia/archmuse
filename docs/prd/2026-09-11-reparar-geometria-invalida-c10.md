# PRD — Reparar la geometría inválida en vez de dejarla pasar (`C-10`)

**Estado:** IMPLEMENTADO · **Fecha:** 2026-09-11 · **Fecha de cierre:** 2026-09-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-11 (R1-R5 completas, unificación de `AM_*` incluida)

> ## Cierre · 2026-09-11
>
> **R1-R5 hechas, suite entera en verde (1.641 pasan, 39 se saltan).** Los siete
> criterios de aceptación de §8, comprobados:
>
> | | Criterio | Resultado |
> |---|---|---|
> | 1 | `plantasimple` se mide | **206 piezas**, 25 viviendas; `coherencia.revisar` ya no revienta |
> | 2 | Su área no cambia | **3.305,18 m²** antes y después |
> | 3 | Los cinco de referencia, pieza a pieza | **+0,0000 m² en los cinco**, congelado en `tests/test_reparacion_geometria_c10.py` |
> | 4 | Cada reparación con su `handle` | 10 en `plantasimple`, todas con handle y `explain_validity` |
> | 5 | La pajarita se sigue descartando | sí, sin tocar su test |
> | 6 | Ningún `Room` inválido | de 10 a **0** |
> | 7 | Suite verde, goldens incluidos | sí; los tres goldens cambian **sólo por claves nuevas**, comprobado con un guardián que rechaza cualquier cambio de valor |
>
> **Un test que decía lo contrario y se ha reescrito, no borrado:**
> `test_capas_am.py::test_inventario_en_modo_heredado_no_excluye_geometria_invalida`
> afirmaba el criterio anterior. Ahora se llama
> `..._aplica_el_mismo_criterio_que_las_capas_am` y su docstring cuenta qué
> decía antes y por qué cambió.
>
> **Y una cifra que conviene no confundir.** Por la vía del comando de AutoCAD
> se reparan **9** y no 10: el payload redondea los vértices a 4 decimales y esa
> redondeo arregla por su cuenta una de las diez degeneraciones. Las dos vías
> miden lo mismo (`C-9`), pero no reparan exactamente lo mismo, y el motivo está
> medido, no supuesto.
>
> **Lo que `C-10` NO ha desbloqueado, y hay que decirlo:** `plantasimple` ya se
> mide, pero **ninguna de sus 25 viviendas publica total** — el desplazamiento de
> 50,00 de los rótulos deja cada pieza a 47-53 m de dos etiquetas de vivienda
> distintas, y `C-5` se niega a repartir lo ambiguo. Eso es lo siguiente, y es
> lo que bloquea CU-2.

> **PRD corto, y con una sola pregunta detrás:** Pablo ya ha firmado el criterio
> (`C-10`, reparar y declarar). Lo que este documento tiene que entregar antes
> de que se toque una línea es **qué cifras cambian**, medidas, y la respuesta a
> la cuarta condición: si el camino `AM_*` se unifica o quedan dos criterios
> distintos para el mismo defecto.
>
> **La respuesta corta, para no enterrarla:** no cambia ninguna cifra. Ni un m²,
> ni una pieza, en ninguno de los cinco planos de referencia. Lo único que
> cambia es que `plantasimple.dxf` **pasa de no medirse a medirse**.

---

## 1. Problema que resuelve

`plantasimple.dxf` no se mide. Mandado entero por la vía del comando —211
polilíneas, 787 textos— el servidor devuelve **HTTP 200 con cero piezas** y un
único hallazgo:

```
GEOSException: TopologyException: side location conflict at -325.82 -292.68
```

**Causa medida:** 10 de los 206 polígonos de `00 areas` son auto-intersecantes,
y `evaluator.evaluate_room_overlap` revienta al intersecarlos. No es el rótulo
—que también está desplazado 50,00, y eso ya se detecta y se declara— ni la
capa: **no hay medición ninguna**.

El origen es una decisión deliberada y escrita en el docstring de
`_closed_polygons_with_color`: el modo heredado **no valida `is_valid`** «para no
excluir de golpe geometría que hoy SÍ se acepta como `Room`». La intención era
buena y el efecto es el contrario del buscado: la geometría no se excluye, entra
rota y tumba la medición entera cuarenta funciones más abajo.

## 2. Usuario afectado

El arquitecto cuyo plano tiene diez polilíneas con un vértice repetido — es
decir, cualquiera. Hoy recibe una excepción de GEOS con coordenadas, que no
significa nada para él, en lugar de su cuadro.

## 3. Objetivo de negocio

`plantasimple.dxf` es **el único proyecto completo del lote** y el que bloquea
el orden de trabajo entero, incluida la beta. Y es el caso general disfrazado de
caso particular: un DXF exportado de un CAD real trae geometría degenerada casi
siempre, así que esto no arregla un fichero, arregla una categoría.

## 4. Objetivo técnico

`C-10`, tal como Pablo lo firmó el 2026-09-11:

> **Un polígono inválido se repara con `make_valid` y la reparación se declara
> siempre. Si `make_valid` cambia el área más allá de la tolerancia, no se
> repara: se descarta, y también se declara.**

Y la razón de que la tolerancia sea el árbitro, medida:

| | Área cruda | Tras `make_valid` | Delta |
|---|---:|---:|---:|
| Los 10 de `plantasimple` | 24,92 · 12,61 · 7,24 · 12,54 · 12,53 · 4,16 · 4,61 · 23,30 · 84,75 · 4,31 | idénticas | **0,000000** |
| La «pajarita» de los tests `AM_*` | 0,0000 | 8,0000 | **8,0000** |

Los diez casos reales son auto-intersecciones **degenerantes** —picos de área
cero, vértices repetidos—: reparar no inventa nada, porque no hay nada que
decidir. Una pajarita de verdad tiene un área ambigua, y ahí ArchMuse no elige:
descarta y lo dice. **La tolerancia separa las dos cosas sin que nadie tenga que
clasificarlas a mano**, que es lo que hace este criterio implementable.

`TOLERANCIA_REPARACION = 0,005 m²` (medio centímetro cuadrado). Los casos reales
dan cero exacto, así que el umbral no está ajustado para que pasen: sobra por
seis órdenes de magnitud.

## 5. Casos de uso

1. **Polilínea con un vértice repetido** → se repara, entra como `Room` con su
   área intacta, y sale un hallazgo que la nombra por su `handle`.
2. **Pajarita real** → no se repara. Se descarta con `MOTIVO_GEOMETRIA_INVALIDA`
   y sale en `geometria_descartada`, como hoy en el camino `AM_*`.
3. **Plano sin geometría inválida** (los cinco de referencia) → no pasa nada, ni
   un hallazgo ni una cifra distinta.

## 6. Casos límite

- **`make_valid` devuelve varias piezas** (`MultiPolygon`, `GeometryCollection`):
  se conservan sólo las partes poligonales y se suman para comparar el área. Si
  la suma está dentro de tolerancia pero hay más de una pieza, **se descarta**:
  un recinto que se parte en dos no es un recinto reparado, es una decisión
  sobre cuál de los dos es la habitación, y ésa no es nuestra.
- **`make_valid` devuelve algo sin superficie** (todo líneas) → descarte.
- **`make_valid` lanza** → descarte, con el motivo.
- **Polígono válido** → no se toca, no se copia y no se declara nada. El camino
  normal no paga esto.

## 7. Flujo del usuario

No cambia. Teclea `ARCHMUSE`, y donde antes veía una excepción de GEOS ahora ve
su cuadro y una línea que dice cuántas polilíneas suyas se han reparado para
poder medirlas, con sus `handle` para ir a mirarlas.

## 8. Criterios de aceptación

1. `plantasimple.dxf` se mide: `coherencia.revisar` deja de reventar. **Medido
   ya con el parche en memoria: 25 viviendas y 272 hallazgos, en 10,6 s.**
2. **El área total no cambia**: 3.305,18 m² antes y después en `plantasimple`.
3. **Ninguno de los cinco planos de referencia cambia nada.** Medido pieza a
   pieza: `ejemplo` 40 → 40 piezas y 369,4734 m² → 369,4734 m²; `v1plantas`,
   `v2s`, `v3s` 8 → 8 y 66,3286 → 66,3286; `V5` 22 → 22 y 191,3194 → 191,3194.
   **Delta +0,0000 m² en los cinco.**
4. Cada reparación produce un hallazgo con el `handle` del polígono.
5. La pajarita de `tests/test_capas_am.py` **sigue descartándose**, sin tocar ese
   test.
6. Ningún `Room` sale con `polygon.is_valid == False`. Hoy salen 10 en
   `plantasimple`; después, 0.
7. La suite entera sigue en verde, **incluido el golden `plano.coherencia`**.

## 9. Riesgos

- **El riesgo real no es medir de más: es medir distinto sin enterarse.** Por eso
  el criterio 3 es pieza a pieza y no sólo el total — dos errores que se
  compensan dan el mismo total.
- **Coste**: `make_valid` sólo se llama sobre polígonos ya inválidos. En el peor
  plano disponible son 10 de 206.
- **`make_valid` depende de la versión de GEOS.** Con `shapely==2.1.2` fijado en
  `requirements.txt` está congelado; el día que suba, el criterio 3 es el que lo
  detecta.

## 10. Impacto sobre módulos existentes

- `analyzer/parser.py` — `_closed_polygons_with_color` (modo heredado) y
  `_leer_capa_am` (capas `AM_*`) pasan a compartir **una sola** función de
  reparación. `PlanoLeido` gana la lista de reparaciones.
- `analyzer/coherencia.py` — tipo nuevo `GEOMETRIA_REPARADA`.
- `app.py` — la lista viaja en la respuesta, junto a `geometria_descartada`.
- `autocad/archmuse.lsp` — la imprime antes de medir, como ya hace con los
  descartes.

## 11. Plan de implementación

| | Tarea | ≤2 h |
|---|---|---|
| R1 | `reparar_poligono()` en `parser.py`: `make_valid`, partes poligonales, regla de la tolerancia. Tests unitarios con la pajarita y con un vértice repetido | sí |
| R2 | Engancharla en `_closed_polygons_with_color` **y** en `_leer_capa_am` (§14.1), con el inventario de reparaciones | sí |
| R3 | `GEOMETRIA_REPARADA` en `coherencia.py` + el hallazgo con `handle` | sí |
| R4 | Que viaje en la respuesta del endpoint y la imprima el `.lsp` | sí |
| R5 | Regresión: los cinco planos de referencia, pieza a pieza, contra las cifras del criterio 3 | sí |

## 12. Plan de pruebas

Lo de §8, y uno que no es obvio: **un test que congele las cifras de los cinco
planos de referencia pieza a pieza**, no sólo el total. Es lo que convierte el
criterio 3 en algo que sigue vigente dentro de seis meses en vez de en una
comprobación que se hizo una tarde.

## 13. Métricas

Cuántas polilíneas se reparan por plano en la beta. Si en los planos del primer usuario
la cifra es alta, la geometría degenerada es la norma y no la excepción, y eso
cambia qué hay que endurecer después.

## 14. Posibles motivos para NO implementar

**14.1 · La cuarta condición de Pablo: sí, hay que unificar `AM_*`, y sale
gratis.**

Hoy el mismo defecto tiene dos criterios: el camino `AM_*` **descarta** con
`MOTIVO_GEOMETRIA_INVALIDA` y el heredado **deja pasar**. Con `C-10` serían
tres, que es peor. La unificación es segura y está medida: la única geometría
inválida que hay en los tests `AM_*` es la pajarita
(`[(0,0),(4,4),(4,0),(0,4)]`), y su delta de área es **8,0000** — muy por encima
de la tolerancia, así que **`C-10` la descarta exactamente igual que hoy**. Los
tests de `test_capas_am.py` y `test_coherencia.py` que la esperan descartada
siguen en verde sin tocarlos.

Dicho de otro modo: unificar no relaja el criterio de `AM_*`, lo **explica**.
Hoy `AM_*` descarta toda geometría inválida porque no sabía distinguir; con la
tolerancia, distingue.

**14.2 · El argumento honesto en contra.** Que ArchMuse toque la geometría del
arquitecto es una línea que hasta hoy no se cruzaba, y cruzarla por diez
polilíneas de un plano es un precedente. La respuesta —y es la que hace que
merezca la pena— es que **aquí no se está decidiendo nada**: el área no cambia,
en ninguno de los diez casos, ni en el sexto decimal. Cuando cambia, no se
repara. La reparación que `C-10` autoriza es exactamente la que no tiene
contenido profesional; en cuanto lo tiene, el criterio se retira y pregunta.

**14.3 · Lo que este PRD NO autoriza**, y conviene dejarlo escrito antes de que
alguien lo dé por incluido: cerrar polilíneas abiertas, unir extremos próximos,
simplificar vértices, quitar solapes entre recintos, ni ninguna otra «limpieza»
de geometría. Sólo `make_valid` sobre lo ya inválido, y sólo cuando el área no
se mueve.

---

**Decisión:** _pendiente de revisión por Pablo_
