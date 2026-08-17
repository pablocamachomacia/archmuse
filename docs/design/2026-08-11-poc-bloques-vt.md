# PoC — geometría en las definiciones BLOCK VT01..VT25 de `ejemplo.dxf`

**Fecha:** 2026-08-11 · **Tipo:** PoC desechable, sin implementación de producto · **Estado:** para decisión

Continúa el informe [2026-08-10-importacion-de-proyectos.md](2026-08-10-importacion-de-proyectos.md).
Aquel informe midió que el modelspace de `ejemplo.dxf` solo contiene el 0,4 %
de la geometría del fichero (219 de 53.500 entidades) y 0 `INSERT`. Esta PoC
mide qué hay exactamente en el otro 99,6 % — las 25 definiciones de bloque
`VT01`..`VT25` — y si merece la pena leerlo.

Código: [`experimentos/poc_bloques_vt.py`](../../experimentos/poc_bloques_vt.py),
desechable, no importado desde ningún módulo de producción ni test.
Todas las cifras de este documento salen de ejecutarlo, no están estimadas.

---

## 0. Resumen ejecutivo

Las 25 definiciones `VTxx` son planos completos de vivienda (muros, puertas,
ventanas, sanitarios, mobiliario) con **40 veces más geometría** que todo el
modelspace. Pero **ninguna está insertada en ningún sitio** (0 `INSERT` en
todo el fichero) y cada una vive en su **propio sistema de coordenadas
local**, sin relación numérica con el modelspace. Se puede reconstruir el
plano detallado de **una vivienda tipo aislada**; no se puede reconstruir
el edificio, porque el dato de "qué vivienda va dónde" no está en este
fichero — no es que el parser no lo lea, es que no existe.

---

## 1. ¿Cuánta geometría adicional recuperamos frente al parser actual?

| | Modelspace (ya leído por `parser.py`) | Bloques `VT01..VT25` |
|---|---:|---:|
| Entidades | 219 | 8.877 (directas) / 14.515 (con mobiliario/puertas/ventanas expandidos) |
| `INSERT` | 0 | 344 (mobiliario + carpinterías, uno por instancia) |
| Factor | 1× | **×40,5** sobre entidades directas |

`analyzer/parser.py` no toca `doc.blocks` en ningún punto — confirmado
leyendo el módulo, no solo por el resultado. Solo recorre el modelspace vía
`_recorrer_plano()`, que sí sabe descender por `INSERT` (`virtual_entities()`,
añadido para otro caso), pero nunca se dispara aquí porque no hay ningún
`INSERT` que recorrer.

## 2. ¿Qué elementos arquitectónicos podemos reconocer?

Por convención de capa, consistente en las 25 definiciones:

| Capa | Contenido | Entidades (agregado 25 bloques) |
|---|---|---:|
| `00 MURO` | Muros: contorno en `LWPOLYLINE` (abiertas en su mayoría) + segmentos en `LINE` | 2.248 |
| `00 PUERTA` / `00 PUERTAS` | Hoja y arco de puerta (bloque anidado `puerta 82`, reescalado por instancia) | 2.288 + 574 |
| `00 vidrio` | Vidrio de ventana (parte del bloque anidado `vdntestre`, junto con el marco en `00 MURO`) | 608 |
| `00 SANITARIOS2` | Inodoro, lavabo (bloques anidados `inodoro`, `LAVABO_ESCALA_20`) | 169 |
| `00 muebles` | Mobiliario (sillón, sillas) | 309 |
| `00-INST` | Cocina, fregadero, y **etiquetas de instalación** (`F`, `FR`, `LV`, `V`, `LD`, `H` — fregadero/frigorífico/lavabo/váter/lavadora/horno, sin confirmar la leyenda exacta, **PENDING**) | 260 |
| `00 tramas` | Rayado/hatch de muro (patrones `LINE`, `CROSS`) | 49 |
| `00 puntos` | Sin identificar con certeza (cotas o puntos de replanteo) — **PENDING** | 509 |

Puertas y ventanas se reconocen por **símbolo reutilizado**, no por atributo
explícito: `puerta 82` (arco + jambas) y `vdntestre` (marco + vidrio) son un
único bloque cada uno, insertado muchas veces con distinta escala y rotación
— la escala de la instancia es el ancho real de esa puerta/ventana concreta,
no un valor fijo. Conteo por nombre de bloque anidado (heurística por
substring, no un catálogo cerrado): **62 puertas**, **44 ventanas** en las 25
viviendas — orden de magnitud razonable (~2,5 puertas y ~1,8 ventanas por
vivienda), pero es un mínimo: pueden existir otros símbolos de puerta/ventana
con nombre distinto no capturados por esta heurística. Longitud de muro:
**1.077,8 m** sumando solo las `LINE` de la capa `00 MURO` — excluye las
`LWPOLYLINE` de esa misma capa, así que es también un mínimo, no el total.

## 3. ¿Podemos reconstruir viviendas individuales?

**Sí, geométricamente, una a una.** Cada `VTxx` es autocontenida: expandiendo
sus `INSERT` de un nivel se obtiene el plano completo de esa vivienda tipo
— muros, huecos, sanitarios, mobiliario — con superficie bruta (bounding box)
de 64 a 136 m² según el tipo, coherente con superficies reales de vivienda.

Lo que **no** hay dentro del bloque es la separación en estancias: los únicos
`MTEXT` dentro de `VT01` son las seis etiquetas de instalación de un cuarto
húmedo (`F`, `FR`, `LV`, `V`, `LD`, `H`), no nombres de estancia
("Dormitorio", "Salón"...), y ninguna de sus 28 `LWPOLYLINE` cerradas está
etiquetada como recinto individual. Los nombres de estancia
("Dormitorio 1", "Salón/cocina"...) solo existen en el modelspace, asociados
a los 53 polígonos de la capa `00 areas` que ya lee `parser.py` — no dentro
del bloque. Reconstruir la partición en habitaciones a partir de la
geometría de muros del bloque (cerramiento de polígonos por eje de muro)
es un problema geométrico real y no trivial, no resuelto por esta PoC — es
trabajo futuro, no un vacío de datos.

La relación "rótulo `VTn/m` del modelspace ↔ definición `BLOCK VTxx`" solo
existe por **coincidencia de nombre** (`VT1` en el modelspace, `VT01` como
bloque) — comprobado para los 7 rótulos presentes en el cuadro de
superficies del modelspace (`VT1/3`, `VT2/2`, `VT3/3`, `VT4/2`, `VT5/1`,
`VT6/2`, `VT22/1`), todos con bloque `VTxx` correspondiente. El significado
exacto de la fracción (`VT1/3`) no está confirmado — junto a cada rótulo
aparece un texto "N uds." (p. ej. "8uds." junto a `VT1/3`), compatible con
"N viviendas de este tipo en el edificio", pero no verificado — **PENDING**.
Un intento de contrastar el área del bloque `VT01` contra el polígono
`00 areas` más cercano a la etiqueta `VT1/3` del modelspace no dio una
correspondencia clara (el polígono más próximo mide 4,0 m², muy por debajo
de la superficie bruta del bloque, 109,6 m²) — la etiqueta del modelspace
está posicionada junto a la tabla resumen de la unidad, no junto a su
polígono de superficie, así que este cruce automático por proximidad
**no sirve tal cual** y necesitaría lógica dedicada — **PENDING**, no
bloqueante para esta fase.

## 4. ¿Podemos reconstruir el edificio completo?

**No, con este fichero.** No es una limitación del parser: no existe en el
DXF ningún dato de posición, planta o rotación para ninguna de las 25
viviendas. La prueba: 0 `INSERT` en todo el fichero — ni en modelspace, ni
anidados entre bloques `VTxx` (los únicos `INSERT` que hay son mobiliario y
carpinterías *dentro* de cada vivienda, resueltos en la sección 2). Sin
`INSERT`, no hay matriz de transformación, y sin transformación, "dónde va
esta vivienda dentro del edificio" es un dato que **no existe en el archivo,
no que el importador no sepa leer**.

Confirmación adicional: los bounding boxes de las 25 definiciones son casi
todos coordenadas cercanas al origen local del bloque (0,0) — sistemas de
coordenadas independientes entre sí, no una posición real compartida — con
una excepción (`VT04`, bbox en torno a (8839, 503)) que confirma que ni
siquiera "cerca del origen" es una convención fiable al 100 %.

## 5. ¿Qué información falta irremediablemente por los 0 `INSERT`?

- Posición y rotación de cada vivienda dentro del edificio.
- Planta/nivel al que pertenece cada vivienda (más allá de lo que ya
  aparece, sin confirmar, en el cuadro del modelspace).
- Número de repeticiones reales construidas de cada tipo, con certeza (el
  "N uds." del modelspace es el candidato, no confirmado — PENDING).
- Contorno del edificio completo y adyacencias entre viviendas.

Nada de esto es recuperable leyendo mejor el DXF: **no está escrito**.
Cualquier intento de "adivinarlo" (p. ej. distribuir viviendas en una
cuadrícula por su área) sería inventar un ensamblaje que el arquitecto no
dibujó — exactamente lo que el informe anterior y esta PoC piden evitar.

## 6. ¿Qué arquitectura debería tener el futuro importador DXF?

Confirma, con datos, la arquitectura de 3 niveles ya propuesta en el informe
de 2026-08-10 — no cambia, se refina el Nivel 0:

- **Nivel 0 (Lector):** hoy solo recorre modelspace. Debe recorrer también
  `doc.blocks`, con dos modos: (a) blocks referenciados por `INSERT` — vía
  `virtual_entities()`, patrón que `_recorrer_plano()` ya implementa; (b)
  blocks **no referenciados** que parezcan una unidad completa (heurística:
  contienen entidades en capas de muro/puerta/ventana, superficie bruta en
  rango de vivienda) — caso nuevo que esta PoC confirma que existe y no es
  marginal (25 de 25 bloques VT de este fichero caen en este caso).
- **Nivel 1 (Reconocedor):** por capa → tipo arquitectónico (muro, hueco,
  sanitario...), igual que ya hace `parser.py` con `00 areas` — extender el
  mismo patrón a `00 MURO`/`00 PUERTA`/`00 vidrio`, no inventar uno nuevo.
- **Nivel 2 (Perfil de convención):** el nombre de capa (`00 areas`,
  `00 MURO`...) y el nombre de bloque de puerta/ventana son de este estudio
  concreto — exactamente el mismo patrón que `capas_candidatas()` /
  `CapaIndeterminada` ya resuelve para `AREA_LAYER`. No hay que diseñar nada
  nuevo, hay que generalizar lo que ya existe a más capas.

Ninguna pieza de esta arquitectura intenta ensamblar el edificio: el
ensamblaje sigue siendo un dato de entrada que hay que pedir (ver informe de
2026-08-10, sección de muestra real), no algo que el importador deba
inferir.

## 7. ¿La estrategia de leer definiciones BLOCK merece pasar a producción?

**Sí, con alcance acotado — no como importador general todavía.** El caso de
uso que justifica el esfuerzo, con datos de esta PoC: **catálogo de vivienda
tipo** — muchos despachos entregan, además del edificio ensamblado, un DXF
con la "librería" de tipos de vivienda (justo lo que es este fichero). Leer
esas definiciones da, por vivienda tipo, sin ensamblar nada: superficie
bruta, número de huecos, longitud de muro — hechos `Hecho`-tipados,
consistentes con el resto del motor.

No merece la pena todavía generalizar la heurística de "qué bloque es una
vivienda completa" (sección 6, Nivel 0b) más allá de un caso piloto: con un
solo fichero real no se puede distinguir señal de coincidencia. Necesita
contrastarse contra los proyectos reales pedidos en el informe anterior
antes de escribir código de producción.

## 8. ¿Qué deberíamos probar con los primeros proyectos reales?

1. **¿El patrón "bloques de vivienda sin `INSERT`" se repite** en otros
   despachos, o es un hábito de este estudio concreto?
2. **¿Los DXF de obra real sí tienen `INSERT`** (edificio ya ensamblado), a
   diferencia de este DXF de catálogo de tipos — confirmaría que hacen falta
   dos casos de uso distintos, no uno.
3. **¿Los nombres de capa de muro/puerta/vidrio son estables** entre
   estudios, o cada uno usa los suyos (como ya se sabe que pasa con
   `AREA_LAYER`)?
4. **¿Existe siempre un cuadro de superficies en el modelspace** (como el de
   este fichero) que sirva de "verdad" contra la que contrastar lo leído de
   los bloques?

---

## Siguiente paso recomendado

Ninguno todavía sin decisión de Pablo — esta PoC es un cierre de fase, no
abre trabajo nuevo. Candidatos, sin empezar:

- Recopilar la muestra real (5-8 proyectos, ≥3 estudios) pedida en el
  informe de 2026-08-10 — sigue siendo el bloqueo real para ir más allá de
  esta PoC.
- Si Pablo quiere una CAP de producto sobre esto: requiere PRD primero
  (regla de proceso del repo), y su alcance mínimo razonable según esta PoC
  sería "superficie bruta y conteo de huecos por vivienda tipo a partir de
  bloques no insertados", no un importador general.
