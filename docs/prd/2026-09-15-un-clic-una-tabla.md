# PRD — Un clic, una tabla: medir la vivienda que está al lado del punto

**Estado:** Aprobado en el encargo · **Fecha:** 2026-09-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, en el mismo encargo («Trabaja de forma autónoma. PRD primero»), con sus ocho condiciones. El criterio nuevo (`C-17`) queda **propuesto, pendiente de firma**.

---

## 1. Problema que resuelve

En un plano con varias viviendas —el maestro de un estudio: 677 recintos, 27
viviendas— ARCHMUSE mide la planta entera, prepara la tabla de todas y al final
le pregunta al arquitecto de cuál la quiere con una lista numerada. Tres dolores,
los tres medidos o vistos:

- **Lento.** 413 s el 15-sep por la mañana; 17 s de servidor tras el arreglo de
  la tarde, más 6-8 s leyendo el dibujo. Para dibujar UNA tabla.
- **Al revés de cómo trabaja.** El arquitecto sabe dónde está la vivienda: la
  tiene delante. Elegirla de una lista de 27 rótulos, varios repetidos, es
  traducir su plano a nombres.
- **Repetido.** Para la siguiente vivienda, otra vez todo el plano.

Lo pide Pablo: «el usuario hace UN clic al lado del dibujo de una vivienda y
ArchMuse mide SOLO esa vivienda y dibuja su tabla rellena en ese punto. Luego
repite con la siguiente. Un clic, una tabla.»

## 2. Usuario afectado

El arquitecto de la beta, con planos maestros de varias viviendas en AutoCAD.
Hoy, el primer usuario de la beta.

## 3. Objetivo de negocio

Que medir un bloque entero sea hacer clic N veces, y no esperar N veces a que se
mida el bloque. Es la diferencia entre una herramienta que se usa en cada entrega
y una que se prueba una vez.

## 4. Objetivo técnico

1. El clic elige la vivienda: la más cercana al punto. Si hay duda, no mide y lo
   dice (`C-17`, en el espíritu de `C-5` y `C-15`: ante la duda no se elige).
2. **Menos de 10 s en total**, aunque el plano tenga muchas viviendas.
3. **Las cifras de esa vivienda son idénticas** a las de medirla dentro de la
   planta entera, y a las de medirla sola en un plano con sólo ella.
4. **Nunca acaba en silencio**: dice qué ha dibujado o por qué no.

### Lo que viaja al servidor, y por qué no es «sólo lo de esa vivienda» al pie de la letra

**Medido el 2026-09-15 en AutoCAD Core Console sobre una copia del maestro**
(677 recintos, 6.280 textos, 9.220 polilíneas en otras capas):

| Qué lee el `.lsp` | Tiempo |
|---|---|
| Recintos de la capa, con vértices | 0,23 s |
| Textos, con posición | 1,47 s |
| Polilíneas de otras capas, en JSON | **4,94 s** |
| Polilíneas de otras capas, sólo su caja (sin JSON) | 0,44 s |

El coste está en las polilíneas de otras capas (muros, mobiliario, cotas), y es
lo que se recorta: **sólo viajan las que están cerca de un rótulo de superficie
construida**, que son las únicas que la medición mira (`C-12`).

**Los recintos y los textos de toda la planta sí viajan**, y es una decisión
deliberada, no una limitación: qué recintos son de qué vivienda (el rótulo
`VT` más cercano), de qué capa salen los nombres de las estancias y si dos
viviendas se llaman igual (`C-13`) se deciden **mirando la planta entera**.
Mandar sólo los recintos de alrededor cambiaría esas decisiones en los bordes
entre viviendas, y la condición 3 —cifras idénticas— dejaría de cumplirse sin
que nadie lo notara. Cuestan 1,7 s y se leen una vez.

**El servidor, medido el 2026-09-15 con el envío de una copia de ese maestro**
(674 recintos, 6.279 textos; sin perfilador):

| Petición | Antes de optimizar | Después |
|---|---|---|
| Medición de la planta entera, con las 9.220 polilíneas de otras capas | 137 s | — |
| La misma, sólo con las de las zonas (en este plano, 0) | 23 s | — |
| 1.ª — de qué vivienda es el clic | — | 2,2 s |
| 2.ª — la medición, con la tabla de una sola vivienda | — | 3,8 s |

Lo que se ha quitado para llegar ahí, **sin cambiar ninguna cifra**:
`medicion._repartos_dudosos` creaba un `Point` por pareja recinto × rótulo
(7,9 s); la misma geometría se escribía dos veces en DXF (2,4 s cada una) y se
leía tres (medición, PDF y tabla), y la tabla se preparaba para las 52 viviendas.

**Total estimado de un clic: unos 8 s** — 1,7 s leyendo recintos y textos, 0,4 s
filtrando las otras capas y 6,0 s de servidor. **Es una suma de medidas, no una
medida de punta a punta en AutoCAD**: la interfaz no se ha probado.

## 5. Casos de uso

- **Bloque de 27 viviendas.** Clic junto a VT2/2 → su tabla en el punto. Clic
  junto a VT3/1 → la suya. Cada una en unos segundos.
- **Planta de una vivienda.** Clic donde sea razonable → su tabla. Igual que hoy.
- **Clic entre dos viviendas.** No mide: dice a cuántos metros está de cada una.
- **Clic lejos de todo.** No mide: dice cuál es la más cercana y a qué distancia.
- **Vivienda con rótulo repetido** (`VT1/3` tres veces). No mide: `C-13` firmado.

## 6. Casos límite

- **El punto cae dentro de una vivienda.** Distancia cero: se mide esa, salvo que
  otra también esté a menos de 1 m (duda).
- **Plano sin rótulos `VT`.** Las viviendas salen del agrupador por proximidad
  («Vivienda 1», «Vivienda 2»): se elige igual, por distancia.
- **Plano con capas de clasificación `AM_*`.** Cambian de dónde salen los
  recintos (`AM_UTIL_INT` sustituye a la capa heredada). El servidor las pide
  **enteras** antes de elegir, y viajan enteras también en la medición.
- **Rótulo de construida con dos polilíneas a su alcance, una lejos de la
  vivienda.** Viaja también la lejana: la zona es el cuadrado del alcance del
  rótulo, no la caja de la vivienda. Sin ella, el rótulo dudoso pasaría por
  inequívoco y saldría una cifra que la planta entera deja vacía.
- **Servidor anterior sin la ruta nueva.** Se dice que el servidor no sabe elegir
  por clic y que hay que reiniciarlo.
- **La elección de la primera petición y la de la segunda no coinciden**
  (imposible con la misma geometría, pero se comprueba): no se dibuja y se dice.

## 7. Flujo del usuario

1. `ARCHMUSE` → xrefs (`C-15`), cuadros, capa: como hoy.
2. «Haz clic al lado de la vivienda que quieres medir (ahí irá su tabla):»
3. «Leyendo el dibujo…» — recintos y textos.
4. Primera petición (`/api/vivienda-en-punto`): el servidor dice **qué vivienda**
   y **qué zonas** necesita de las demás capas, o por qué no mide.
   - «Mido VT2/2: es la más cercana al punto (a 1,20 m; la siguiente, VT2/1, a
     9,80 m).»
   - o «No mido: el punto está a 3,10 m de VT2/2 y a 4,00 m de VT2/1…».
5. El `.lsp` recoge las polilíneas de otras capas que tocan esas zonas.
6. Segunda petición (`/api/medicion-geometria`, con `vivienda`): la medición de
   siempre, que prepara **sólo** la tabla de esa vivienda.
7. Tabla dibujada en el punto, como hoy, con su marca de borrador (`C-3`).

## 8. Criterios de aceptación

1. Clic junto a cada vivienda de un plano sintético de varias → mide esa.
2. Clic a distancia parecida de dos → no mide y dice las dos distancias.
3. Clic lejos (> 30 m) → no mide y lo dice.
4. Para cada vivienda del plano sintético, la tabla por clic es **idéntica** a la
   de la planta entera y a la de un plano con sólo esa vivienda — incluida la
   fila de construida con un rótulo dudoso cuya segunda polilínea está lejos.
5. Servidor, las dos peticiones, en el plano sintético del tamaño del maestro:
   por debajo de lo que deja el presupuesto de 10 s tras la lectura del `.lsp`.
6. Toda salida del flujo nuevo en el `.lsp` imprime su motivo
   (`tests/test_archmuse_nunca_acaba_en_silencio.py` lo cubre).
7. Nada de planos reales en los tests.

## 9. Riesgos

- **La distancia de duda (2× y 1 m) y la máxima (30 m) son de Claude.** Van en
  `C-17` como propuestos. Pueden ser malas en planos reales: se miden con él.
- **Esc entre las dos peticiones**: el comando dice «Cancelado» (`C-16`, 3.8.1).
- **Sin ejecutar en la interfaz de AutoCAD.** Se prueba en Core Console lo que
  se pueda; el clic y el dibujo, no.

## 10. Impacto sobre módulos existentes

- `analyzer/vivienda_en_punto.py` (nuevo): elección y zonas.
- `analyzer/evaluator.py`: el agrupador por rótulo expone qué rótulo es cada
  vivienda; su resultado no cambia.
- `app.py`: ruta `/api/vivienda-en-punto`; `_cuadros_de_archmuse` acepta la
  vivienda elegida y prepara sólo la suya.
- `autocad/archmuse.lsp` 3.9.0: el clic, las dos peticiones, las polilíneas por
  zona. `am:elegir-vivienda` deja de usarse en este flujo.
- `docs/design/2026-09-08-criterios-firmados-de-medicion.md`: `C-17` propuesto.

## 11. Plan de implementación dividido en pequeñas tareas

1. `evaluator`: agrupar devolviendo el índice del rótulo.
2. `vivienda_en_punto.elegir` y `zonas` + tests con planos sintéticos.
3. Ruta `/api/vivienda-en-punto` y `vivienda` en la medición + test de identidad.
4. `.lsp` 3.9.0 + tests del fuente + sonda en Core Console.
5. Tiempos, suite, versión.

## 12. Plan de pruebas

`tests/test_un_clic_una_tabla.py` con un generador sintético de varias
viviendas: elección, duda, lejos, `C-13`, identidad con la planta entera y con
la vivienda sola, zona de construida dudosa, capas `AM_*`, tiempo. Tests del
fuente del `.lsp`. La suite entera.

## 13. Métricas para medir el éxito

Tiempo por tabla en el maestro del primer usuario (objetivo < 10 s); número de
«No mido» por duda en una sesión real (si es alto, `C-17` está mal calibrado).

## 14. Posibles motivos para NO implementar la idea

- **Dos peticiones en vez de una** son más piezas que pueden desalinearse. Se
  mitiga comprobando en la segunda que la elección es la misma.
- **La lista de viviendas desaparece de este flujo.** Quien quiera las 27 tablas
  de golpe hace 27 clics. Es lo que se ha pedido; si molesta, se recupera como
  opción, no como flujo por defecto.
- **`C-13` deja fuera las viviendas repetidas, que en un bloque son muchas** (en
  el maestro medido, 7 de 34). El clic las distinguiría por posición, pero `C-13`
  está firmado y no se toca: **pregunta abierta para Pablo**.

---

**Decisión:** aprobado en el encargo del 2026-09-15; `C-17` pendiente de firma.
