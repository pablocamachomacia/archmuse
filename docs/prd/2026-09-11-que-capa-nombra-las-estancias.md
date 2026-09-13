# PRD — Qué capa puede dar nombre a una estancia

**Estado:** APROBADO · **Fecha:** 2026-09-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-11 (opción 1, con la condición dura de §4.2)

> **Criterio firmado, textual:** *«la capa que más nombra, gana. Es medible, no
> inventa vocabulario, y da la respuesta correcta en el único plano donde el
> problema se manifiesta.»*
>
> **Condición dura, textual:** *«si la segunda capa nombra una proporción
> comparable a la primera, NO se elige en silencio. Se declara el reparto y se
> deja que decida el arquitecto, igual que con el desfase.»*

## 1. Problema que resuelve

`parser._capas_de_rotulo` admite hoy como capa de rótulos **cualquiera que ponga
un texto dentro de un recinto**. La idea era separar una capa de nombres de una
de cotas —los textos de cota viven en la línea de cota, nunca dentro de una
estancia— y para eso funciona. Pero no distingue una capa de **nombres** de una
capa de **anotaciones**, y las dos ponen textos dentro.

Se ha visto al alinear los rótulos de `plantasimple.dxf`: de 159 recintos con
nombre, **46 se llaman «F», «FR» o «LD»** — códigos de electrodoméstico de la
capa `00-INST`. El salón de 21,90 m² se llama «F», de frigorífico, y eso deja 23
de 25 viviendas sin total porque no se sabe si «F» es superficie interior o
exterior.

**Es deuda preexistente, no un fallo nuevo.** Mientras los rótulos de ese plano
estaban 50 m por debajo de los recintos, ningún texto caía dentro de nada y la
regla no se notaba. Que haya salido ahora es **suerte, no diseño** — y conviene
dejarlo escrito, porque el mismo tipo de regla («vale cualquiera que cumpla algo
una vez») puede estar en más sitios.

## 2. Usuario afectado

Cualquier arquitecto cuyo plano tenga anotaciones dentro de las estancias, que
es prácticamente cualquiera: mobiliario, instalaciones, sanitarios, cotas
interiores.

## 3. Objetivo de negocio

Desbloquear las viviendas con total de `plantasimple.dxf`, que es lo que hace
falta para CU-2. Y, más allá del caso: que el nombre de una estancia deje de
depender del orden de un `for`.

## 4. Objetivo técnico

### 4.1 · La regla

Entre las capas que hoy se admiten como capas de rótulo, **nombra sólo la que da
nombre a más recintos**. La capa de los recintos sigue admitida siempre (hay
planos que rotulan sobre la propia geometría, como `v1plantas.dxf`).

### 4.2 · El umbral, y por qué ése

**`UMBRAL_CAPA_DE_ROTULOS = 0,5`**: la primera tiene que nombrar **más del
doble** que la segunda. Si no, no se elige nada, se declara el reparto y se
sigue como hasta hoy.

Los datos que lo justifican, medidos el 2026-09-11 sobre los seis planos
disponibles:

| Plano | Capas que nombran recintos | 2ª / 1ª |
|---|---|---:|
| `ejemplo` | `00 TEXTO`: 40 | **0,000** |
| `v1plantas` | `00 areas`: 8 | **0,000** |
| `v2s` | `00 areas`: 8 | **0,000** |
| `v3s` | `00 areas`: 8 | **0,000** |
| `V5` | `00 TEXTO`: 22 | **0,000** |
| `plantasimple` (alineado) | `00 TEXTO`: 111 · `00-INST`: 46 · `00 GRIS`: 2 | **0,414** |

**Lo que dicen estos números.** En cinco de los seis planos hay **una sola** capa
que nombra: el umbral no los toca, valga lo que valga. El único plano con más de
una está en **0,414**, y el ejemplo que Pablo puso como «no holgado» —111 contra
95— estaría en 0,856. Un corte en 0,5 deja el caso real dentro con un margen de
unos diez recintos y el caso dudoso fuera con mucho.

**Y lo que NO dicen, dicho también:** no hay ni un plano medido en la zona
0,4-0,6, así que **0,5 es una convención declarada, no un óptimo medido**. Se
elige ahí porque «más del doble» es una frase que un arquitecto puede discutir,
no porque los datos señalen ese punto. Cuando la beta traiga planos de verdad,
este número es de los primeros que hay que revisar.

### 4.3 · Qué pasa cuando es ambiguo

**No se elige, y no se cambia nada.** Se deja el comportamiento de hoy —todas las
capas admitidas— y se emite un hallazgo con el reparto: «los nombres de este
plano salen de dos capas, `X` (111) e `Y` (95); ArchMuse no elige entre ellas».

Elegir una en el empate sería adivinar; no nombrar nada sería romper planos que
hoy funcionan. Declarar y no tocar es lo único que no es ninguna de las dos.

## 5. Casos de uso

1. **Una sola capa nombra** (los cinco de referencia): nada cambia, ni un
   hallazgo.
2. **Dos capas y una dobla a la otra** (`plantasimple`): nombra la primera; la
   otra deja de nombrar. Se declara qué capa se ha elegido y con qué reparto.
3. **Dos capas parejas**: no se elige, se declara, todo sigue igual.

## 6. Casos límite

- **Ninguna capa nombra ningún recinto** (el `plantasimple` sin alinear): no hay
  nada que elegir y no se declara nada — ese plano ya tiene su propio hallazgo,
  el del desfase.
- **La capa ganadora es la de los recintos**: caso normal de `v1plantas`.
- **Empate exacto**: ambiguo, por definición (ratio 1,0).

## 7. Flujo del usuario

No cambia nada visible salvo que las estancias se llamen como su plano dice. En
el caso ambiguo, un aviso más en la lista de hallazgos.

## 8. Criterios de aceptación

1. Los cinco planos de referencia dan **exactamente los mismos rótulos** que hoy.
2. `plantasimple` alineado: ningún recinto se llama «F», «FR» ni «LD».
3. Con dos capas parejas, no se elige ninguna y se emite el hallazgo.
4. El hallazgo lleva el reparto con cifras, no una frase genérica.
5. La capa elegida consta en `PlanoLeido`, para que el acta la pueda declarar.

## 9. Riesgos

- **Un plano que reparta nombres entre dos capas legítimas** pierde una mitad.
  Es el riesgo que la condición de §4.2 existe para atajar, y por eso el umbral
  es de «más del doble» y no de «una más que la otra».
- **El umbral no está medido en su zona crítica** (§4.2). Riesgo asumido y
  anotado.

## 10. Impacto sobre módulos existentes

`analyzer/parser.py` (`_capas_de_rotulo` y su uso en `leer_plano` /
`build_rooms_from_document`), `analyzer/coherencia.py` (hallazgo nuevo), y el
acta a través de `PlanoLeido`.

## 11. Plan de implementación

| | Tarea |
|---|---|
| N1 | `_elegir_capa_de_rotulos`: recuento, umbral, y el resultado con el reparto |
| N2 | Estrecharlo en `_capas_de_rotulo`, y que `PlanoLeido` lo declare |
| N3 | Hallazgo del caso ambiguo, con cifras |
| N4 | Regresión: los cinco de referencia, rótulo a rótulo |

## 12. Plan de pruebas

El criterio 1 es el que manda: **rótulo a rótulo**, no por recuento. Dos plantas
sintéticas para el caso ambiguo y para el claro.

## 13. Métricas

Cuántos planos de la beta caen en el caso ambiguo. Si son muchos, el umbral está
mal puesto o la regla es insuficiente.

## 14. Posibles motivos para NO implementar

**14.1 · La alternativa que se descarta, y ahora con datos.** El desempate por
cercanía al centroide (la «opción 3» de la conversación) parecía el arreglo más
profundo, porque ataca la causa real —que hoy gana el primero de una lista—.
**Medido fielmente el 2026-09-11**, copiando `match_label_to_room` entera y
cambiando sólo esa línea:

- **cambia 0 rótulos de 0 en los cinco planos de referencia** (`ejemplo`
  incluido: ni una cifra);
- y **cambia 115 de 160 en `plantasimple`, para peor**: el rótulo más próximo al
  centro de una estancia no es su nombre, es **el texto de su superficie**.
  `'F'` → `'21.90m²'`, `'F'` → `'23.38m²'`. Cambiaría un nombre malo por otro
  peor.

Así que la opción 3 es inocua en los planos que funcionan y equivocada en el que
no. Queda descartada **con la medición hecha**, no por intuición.

**14.2 · El argumento honesto en contra de la opción 1.** Sigue siendo una regla
sobre una sola señal —cuántos recintos nombra cada capa— y hay plantas donde esa
señal miente: media planta rotulada en una capa y media en otra, por ejemplo un
plano al que le han pegado un ala de otro proyecto. Para ésas, la respuesta de
este PRD es no elegir y decirlo, que es correcta pero no resuelve nada. La
regla buena de verdad probablemente necesite dos señales, y la segunda no la
tenemos medida todavía.

**14.3 · Lo que este PRD NO autoriza.** Clasificar rótulos por su texto, por su
longitud, por su altura o por su estilo. Sólo por la capa en la que viven y por
cuántos recintos nombra esa capa.

---

**Decisión:** **APROBADO por Pablo el 2026-09-11.**
