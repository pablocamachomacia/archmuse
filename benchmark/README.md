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
Converter o, si no está, con AutoCAD Core Console (`accoreconsole.exe`). Las
variables `ARCHMUSE_ODA` y `ARCHMUSE_ACCORECONSOLE` fijan la ruta si no está en
la de siempre. Sin ninguno de los dos, cada DWG sale como FAIL con ese motivo.

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

1. Se busca su vivienda con la regla de siempre (`reparto_cuadro.elegir_vivienda`:
   por el código de su fila `VIVIENDA TIPO`). Si no se encuentra, todas sus cifras
   quedan como «ArchMuse vacío con motivo», con el motivo del emparejamiento.
2. Las superficies útiles y sus totales salen de `reparto_cuadro.calcular_reparto`
   sobre el cuadro vaciado (`como_plantilla`); la construida cerrada, de la tabla
   de ArchMuse (`C-12`). Si el reparto y la tabla dicen cosas distintas, el plano
   queda PENDIENTE DE REVISIÓN: la comparación no valdría.
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

## Resultado de cada plano

Son criterios del banco, no de arquitectura. Ninguno añade ni cambia un criterio
de medición: lo que ArchMuse deja vacío, lo deja por sus criterios firmados, y
aquí sólo se cuenta. Se aplican en este orden:

| Resultado | Cuándo |
|---|---|
| FAIL | no se ha podido abrir, convertir, leer o medir el plano por un fallo; o hay un MISMATCH clasificado `error de ArchMuse` |
| PENDIENTE DE REVISIÓN | hay un MISMATCH sin clasificar o `pendiente de determinar`, un campo vacío sin motivo, o el reparto y la tabla de ArchMuse no coinciden |
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
