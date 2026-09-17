# Banco de compatibilidad externo

Qué hace ArchMuse, **tal como está hoy**, con planos que no son del estudio con
el que se ha construido. Lee cada plano sin ajustes por plano, anota lo que sale
y, si el plano trae su cuadro de superficies relleno, compara cada cifra.

No es un test del repositorio: los planos son de terceros y **no entran en git**.

## Cómo se ejecuta

1. Crea una carpeta **fuera del repositorio**, por ejemplo `C:\ArchMuse-Benchmark\planos\`.
2. Copia ahí los `.dxf` y `.dwg`, sin subcarpetas. El nombre de fichero da igual:
   no sale en los resultados.
3. Desde la raíz del repositorio:

       venv\Scripts\python.exe benchmark\ejecutar.py C:\ArchMuse-Benchmark\planos

Los DWG se convierten a DXF en un temporal fuera del repositorio con ODA File
Converter o, si no está, con AutoCAD Core Console. Las variables `ARCHMUSE_ODA` y
`ARCHMUSE_ACCORECONSOLE` fijan la ruta si no está en la de siempre. Sin ninguno de
los dos, cada DWG sale como FAIL con ese motivo. **Core Console se lanza por
`herramientas/core_console.py`**, aislado (`/isolate`): lanzado a mano y matado por
un plazo deja FILEDIA a 0 en el AutoCAD de quien lo ejecuta.

El banco se niega a leer planos de una carpeta del repositorio, y a escribir
resultados en él fuera de `benchmark/resultados/`.

## Qué deja

En `benchmark/resultados/` (git lo ignora):

| Fichero | Qué es |
|---|---|
| `AAAA-MM-DD_HHMMSS/resumen.md` | Recuentos, tabla por plano, MISMATCH por clase, patrones repetidos, causas |
| `AAAA-MM-DD_HHMMSS/resultados.csv` | Una fila por plano |
| `AAAA-MM-DD_HHMMSS/detalle.json` | Cada cifra comparada, con su estado y su motivo |
| `AAAA-MM-DD_HHMMSS/mismatches.csv` | Los MISMATCH, con la columna `clase` por rellenar |
| `correspondencia.json` | Qué fichero es cada `plano-NN`. **Sólo aquí** aparece el nombre |
| `clasificacion.csv` | Lo escribes tú: la clase de cada MISMATCH (ver abajo) |

El id `plano-NN` va por el contenido del fichero: añadir planos no cambia el de
los demás.

**Aunque git los ignore, `detalle.json` y `mismatches.csv` llevan cifras y
rótulos de los planos.** No se copian a un issue, a un PR ni a un documento del
repositorio. Lo que se comparte es `resumen.md`, y aun así conviene leerlo antes.

## Qué se compara

Por cada cuadro de superficies del plano:

1. Se busca su vivienda por el código de su fila `VIVIENDA TIPO`, sin espacios y sin
   las letras que el estudio añade tras la tipología («VT13/3FN» es la «VT13/3»). Si
   no se encuentra, todas sus cifras quedan como «ArchMuse vacío con motivo». Si hay
   varias con ese rótulo, se mide cada una como la distinguiría el clic del comando y
   se toma la que mejor coincide: es la que el arquitecto marcaría.
2. Se compara con **la tabla que dibuja ArchMuse** para esa vivienda (la plantilla
   fija: piezas, totales, útil de `C-14` y construida de `C-12`). Cada celda de su
   cuadro va con la fila de su mismo campo; si hay varias filas con el mismo campo
   —dos «Terraza» sin número—, se emparejan **por la cifra**, nunca por el orden.
   *Hasta el 2026-09-17 se comparaba con `reparto_cuadro.calcular_reparto`, un
   camino que el producto dejó de usar con la plantilla fija.*
3. Cada celda con una superficie escrita se compara con una tolerancia de
   **0,01 m²**:

| Estado | Cuándo |
|---|---|
| coincidencia | las dos cifras no se separan más de 0,01 m² |
| MISMATCH | se separan más |
| ArchMuse vacío con motivo | su cuadro tiene cifra y ArchMuse no la da; el motivo es el de ArchMuse |
| referencia inexistente | la celda de su cuadro no tiene una cifra |

Una celda de su cuadro con texto que no es sólo una cifra («-», «N/D») cuenta como
referencia inexistente.

### Clases de MISMATCH

El banco **no clasifica**: copia filas de `mismatches.csv` a `clasificacion.csv`
(columnas `plano,vivienda,campo,clase,nota`) y pon una de estas cuatro clases:

- `redondeo`
- `cuadro desactualizado`
- `error de ArchMuse`
- `pendiente de determinar`

Cualquier otro texto cuenta como sin clasificar.

## Intervenciones: AUTOMÁTICO, UN CLIC o VACÍO

Además, **el banco sí clasifica solo** cada celda comparada según cuánto haría falta
del arquitecto (sólo se mide: ArchMuse todavía no pregunta):

| Categoría | Cuándo |
|---|---|
| AUTOMÁTICO | coincide, o la diferencia está clasificada como `redondeo` o `cuadro desactualizado` |
| UN CLIC | vacía por algo que resolvería una pregunta cerrada: pieza entre dos viviendas, rótulo de construida que alcanza dos polilíneas, cuál de dos contornos es la construida, cuál de dos nombres, interior o exterior, cuál de dos viviendas con el mismo rótulo |
| VACÍO | vacía por algo que ninguna pregunta arregla: estancia dibujada dos veces, contorno que no existe, construida sin rótulo a su alcance, fila que la tabla no tiene… **y cualquier motivo que el banco no reconozca** |

Aparte, *cifras distintas*: MISMATCH sin explicar.

La categoría sale del motivo de ArchMuse (`PATRONES_DE_MOTIVO` en `ejecutar.py`; un
test comprueba que cada fragmento existe en el código). Con varias causas gana la
peor. Un motivo que sólo dice que otra cifra está bloqueada (el útil total, un total
de lado) toma la categoría de lo que lo bloquea.

**Cifras incorrectas (objetivo: 0).** Las cifras distintas de su cuadro sin explicar,
más las filas de la tabla con cifra que su cuadro no respalda (sin celda, o con la celda
vacía). Una vivienda con una de esas filas no cuenta como resuelta. **Límite:** una
estancia bien medida que el arquitecto no puso en su cuadro también cuenta: se revisan
una a una.

El resumen trae, por plano y en total: las tres categorías, **intervenciones por
vivienda** (celdas UN CLIC / viviendas con cuadro: cuenta de más, porque una pregunta
puede resolver varias celdas), **% de viviendas sin ninguna intervención** y **% de
viviendas completas si se respondieran los UN CLIC** (supone que la respuesta basta;
no está medido).

## Resultado de cada plano

Son criterios del banco, no de arquitectura. Ninguno añade ni cambia un criterio
de medición: lo que ArchMuse deja vacío, lo deja por sus criterios firmados, y
aquí sólo se cuenta. Se aplican en este orden:

| Resultado | Cuándo |
|---|---|
| FAIL | no se ha podido abrir, convertir, leer o medir el plano por un fallo; o hay un MISMATCH clasificado `error de ArchMuse` |
| PENDIENTE DE REVISIÓN | hay un MISMATCH sin clasificar o `pendiente de determinar`, o un campo vacío sin motivo |
| FAIL | tiene cuadro con cifras y ArchMuse no da ninguna igual; o no tiene cuadro y ArchMuse no ha sabido leerlo (capa o escala sin resolver) |
| SIN REFERENCIA | no tiene un cuadro con cifras; se anota la cobertura |
| PARTIAL | hay MISMATCH explicados (`redondeo`, `cuadro desactualizado`), campos vacíos con motivo, o cuadros sin vivienda emparejada |
| PASS | todas las cifras de su cuadro coinciden |

**Un MISMATCH sin explicar nunca da PASS.**

### Columnas de `resultados.csv`

| Columna | Qué cuenta |
|---|---|
| `viviendas_detectadas` | viviendas que mide ArchMuse |
| `viviendas_con_cuadro` | cuadros de superficies encontrados en el plano |
| `viviendas_emparejadas` | cuadros cuya vivienda se ha encontrado |
| `viviendas_correctas` | viviendas emparejadas en las que todas las cifras comparadas coinciden |
| `estancias` | piezas medidas |
| `superficies` | cifras que da la tabla de ArchMuse (piezas, totales y construida) |
| `campos_vacios` | cifras que la tabla deja vacías, piezas sin fila y viviendas sin tabla |
| `preguntas` | preguntas que ArchMuse haría al arquitecto |
| `errores` | fallos inesperados |
| `tiempo_s` | lectura, medición y comparación; sin la conversión |

## Qué no mide

Mide el **motor** de ArchMuse —lector DXF, medición y reparto— sobre el fichero
entero. **No mide la integración con AutoCAD** (`C-7`): el comando lee el dibujo
con `ssget` y manda la geometría, y lo que se pierda en ese camino no aparece
aquí. Un PASS dice que el motor sabe medir ese plano, no que el comando lo haga.

Tampoco elige capa ni escala a mano: si ArchMuse no las resuelve solo, el plano
sale con esa pregunta como motivo. Adaptar ArchMuse plano por plano falsearía el
banco.

## Después de ejecutarlo

Se analizan **los patrones que se repiten** (sección del resumen) y, sólo
después, se propone el cambio mínimo. Un fallo que sale en un único plano se
anota, no se arregla por su cuenta.
