# Fixtures derivados de planos reales

Estos dos DXF **no son planos de cliente**. Son ficheros **reconstruidos** a
partir de dos planos reales, y contienen sólo dos cosas: la geometría de los
recintos y el texto de sus rótulos.

## Por qué no está aquí el plano original

Este repositorio es **público**, y el `.gitignore` lo dice con su motivo: *«un
plano de cliente commiteado por descuido es una fuga de datos que el historial
no olvida»*. La excepción `!tests/fixtures/**/*.dxf` existe para los bancos
sintéticos, así que **es justo aquí donde la red de seguridad no salta** y hay
que poner el cuidado a mano.

## Cómo se han hecho, y por qué no borrando capas

`scripts/derivar_fixture_anonimo.py` **no abre el original y borra lo que
sobra**: lee el plano con el mismo `parser.leer_plano` del producto, se queda
con los polígonos y los rótulos, y escribe un DXF **nuevo** empezando de cero.
Todo lo que no se copia explícitamente no existe en la salida porque nunca
llegó a existir.

La diferencia no es teórica. El original de `planta_tres_viviendas.dxf` traía
`$LASTSAVEDBY = '<nombre omitido>'` en la cabecera — **el nombre de pila de quien lo
guardó**, que ningún borrado de capas habría quitado. En el derivado esa
variable vale `ezdxf` y los dos GUID del documento son nuevos.

`scripts/auditar_fixture_anonimo.py` comprueba el resultado como si viniera de
un desconocido: cabecera entera, capas apagadas y congeladas, definiciones de
bloque insertadas o no, estilos, todo el texto de todas las entidades de todos
los layouts y bloques, `XDATA`, diccionarios y propiedades del documento.

**Qué queda, y es todo:** rótulos de estancia («Salón/cocina», «Dormitorio 1»,
«Terraza», «Tendedero», «Baño», «Aseo») y códigos de tipología `VT<n>/<m>`. Los
primeros son vocabulario común de cualquier vivienda; los segundos son códigos
de vivienda tipo, no nombres de promoción. Sin ellos no se puede probar el
reparto por rótulos, que es la mitad de lo que estos ficheros vigilan.

**Qué no queda:** cajetín, carátula, definiciones de bloque (las del original
venían de un export de Revit y llevaban códigos de vivienda del proyecto),
capas del estudio, cotas, mobiliario, carpintería, sombreados, `XDATA`, y el
nombre de quien guardó el fichero. De 19,5 MB a 33 KB.

## Los dos ficheros

| Fichero | Qué caso cubre | Verdad conocida |
|---|---|---|
| `planta_tres_viviendas.dxf` | La planta que **sí** se mide entera | VT1/3 = 58,78 int / 7,54 ext · VT2/2 = 50,97 / 7,47 · VT3/3 = 59,11 / 7,45. Planta: 168,86 int / 22,46 ext. 22 piezas. Y un rótulo `VT22/1` sin recintos, que advierte sin bloquear |
| `vivienda_con_solapes.dxf` | La rama **bloqueada**: 7,08 m² dibujados dos veces (4,00 entre los dos tendederos, 3,08 entre terraza y tendedero) | Ninguna superficie publicable, las 9 piezas medidas igual |

Los dos miden **exactamente** lo mismo que sus originales, comprobado pieza a
pieza al derivarlos. Si un cambio los mueve, ha movido la medición de un plano
real.

> **Nota de procedencia (2026-09-08).** El segundo fichero se deriva del plano
> `v2s`, no del DXF que falló en la sesión con el arquitecto: ese fichero
> todavía no estaba disponible. Se ha elegido porque cubre la rama bloqueada,
> que la planta de tres viviendas no ejercita. **No sustituye** al fixture que
> hará falta para reproducir el fallo del «Tendedero» duplicado ni el del
> «Baño» en `sin_clasificar`.
