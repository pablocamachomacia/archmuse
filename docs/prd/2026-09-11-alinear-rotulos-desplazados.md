# PRD — Alinear los rótulos desplazados, sólo si él lo dice

**Estado:** APROBADO · **Fecha:** 2026-09-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-11

> **Por qué este PRD existe siendo tan pequeño.** Lo que se decide aquí no es
> una función: es **la primera vez que ArchMuse mueve algo del dibujo de otro**,
> aunque sea sólo en memoria y sólo durante una medición. Esa línea merece
> quedar firmada, con su alcance escrito, para que dentro de seis meses nadie
> la ensanche dando por hecho que ya estaba cruzada.

## 0. Lo que Pablo firmó, textual

> 1. El comando detecta el desfase, lo declara con la cifra exacta, y
>    **PREGUNTA**: «los rótulos de este plano están 50,00 por debajo de los
>    recintos. ¿Los alineo solo para esta medición? Tu dibujo no se toca.» Con
>    `Si` explícito, por defecto `No`.
> 2. Si dice que sí: se mide con los rótulos alineados, y **el acta lo declara
>    como corrección aplicada, con la cifra**. No puede quedar una medición que
>    dependa de un desplazamiento sin que conste.
> 3. Y en el mismo mensaje, la recomendación: «si esto no es intencionado, un
>    `DESPLAZA` de 0,-50 en tu AutoCAD lo arregla para siempre y no tendré que
>    preguntártelo más».
>
> **Condiciones duras:**
> - **Nunca se aplica sin preguntar**, ni siquiera si la detección es unánime.
>   Este plano tiene dx=0 exacto y meseta limpia, y aun así se pregunta: **la
>   certeza técnica no sustituye su permiso.**
> - **Si el desfase no es limpio** (varias traslaciones candidatas, o votos
>   repartidos), **no se ofrece**: se declara y se para. Ofrecer un
>   desplazamiento dudoso es peor que no ofrecer ninguno.
> - **No tocar el DXF en disco bajo ningún concepto.**

## Estado de ejecución (2026-09-11)

| | Tarea | Estado |
|---|---|---|
| A1 | `limpio` en el detector | **HECHA**. `plantasimple`: explica 199/200, 0 competidoras, `limpio=True` |
| A2 | Alineación en memoria | **HECHA**. Hash del DXF idéntico antes y después |
| A3 | Que la corrección llegue al acta | **PARADA**, ver abajo |
| A4 | El `.lsp`: preguntar y volver a medir | **PARADA**, ver abajo |
| A5 | Regresión de los cinco de referencia | **HECHA**. Idénticos con y sin el parámetro |

16 tests en `tests/test_alinear_rotulos.py`. Suite entera: 1.657 pasan.

> ### A3 y A4 paradas a propósito: alinear destapa otro problema
>
> Con la alineación puesta, `plantasimple` pasa de **0 recintos con nombre a
> 159 de 160**. Pero de esos 159:
>
> | Capa que da el nombre | Recintos | Ejemplos |
> |---|---:|---|
> | `00 TEXTO` | 111 | Salón/cocina, Dormitorio 1, Baño, Terraza, Tendedero |
> | **`00-INST`** | **46** | **«F», «FR», «LD»** — códigos de electrodoméstico |
> | `00 GRIS` | 2 | «ESPACIO TRANSFERENCIA» |
>
> Y el efecto en la medición: viviendas con total pasa de 0 a **2 de 25**, y el
> impedimento de las otras 23 es literalmente *«3 pieza(s) no se sabe si son
> superficie interior o exterior por su rótulo («F» 21,90 m²)»* — **21,90 m² es
> el salón**, que se ha quedado llamándose «F» de frigorífico.
>
> **La causa no es la alineación**: es que `parser._capas_de_rotulo` admite como
> capa de rótulos *cualquiera que ponga un texto dentro de un recinto*. Mientras
> los rótulos estaban a 50 m, ningún texto caía dentro de nada y la regla no se
> notaba. Es una debilidad que existía antes y que esta tarea ha destapado, no
> una que haya creado.
>
> **Por qué se para aquí y no se arregla de paso.** Decidir qué capa puede dar
> nombre a una estancia —y cuál de dos textos dentro del mismo recinto gana— es
> criterio profesional (`D-7`), y el cierre de `CLAUDE.md` lo nombra
> explícitamente: «dos textos dentro de un recinto y uno gana… si no se
> encuentra la línea donde eso se decidió a propósito, es que no se decidió».
> Hoy lo decide el orden de un `for`. Elegir el criterio bueno sin firmarlo
> sería exactamente lo que este proyecto tiene prohibido.
>
> **Y sobre todo: ofrecer A4 hoy sería ofrecerle al arquitecto que alinee su
> plano para que su salón se llame «F».** Eso es peor que no ofrecer nada, que
> es el mismo argumento con el que se descartó ofrecer un desfase dudoso.

## 1. Problema que resuelve

`plantasimple.dxf` ya se mide (`C-10`), pero **ninguna de sus 25 viviendas
publica total**: los rótulos están 50,00 unidades de dibujo por debajo de las
polilíneas de área, así que cada pieza queda a 47-53 m de dos etiquetas de
vivienda distintas y `C-5` se niega —con razón— a repartir lo ambiguo. El plano
mide 206 piezas y no sabe cómo se llama ninguna.

Hoy ArchMuse ya **detecta** el desfase y lo declara (hallazgo
`coherencia.ROTULOS_DESPLAZADOS`, con `aplicado: False`). Lo que falta es qué
hacer con esa información, y hay exactamente dos cosas que se pueden hacer: una
que le sirve hoy y otra que le arregla el plano para siempre. Se ofrecen las
dos.

## 2. Usuario afectado

El arquitecto delante de un plano suyo que ArchMuse mide bien y no sabe nombrar.
Hoy recibe un aviso correcto y ninguna salida.

## 3. Objetivo de negocio

Desbloquear CU-2 (cuadro↔vivienda) contra los 25 cuadros reales de
`plantasimple.dxf`, que es el primer examen con más de un cuadro por plano. Sin
viviendas con cifras no hay nada que emparejar.

## 4. Objetivo técnico

- El desplazamiento se aplica **a los rótulos, en memoria, durante una
  medición**. Nunca al fichero, nunca a la geometría, nunca por defecto.
- Se aplica **sólo** cuando el cliente lo pide explícitamente **y** la detección
  es limpia. Las dos condiciones, no una.
- Cuando se aplica, **consta en el acta como corrección, con la cifra**, del
  mismo modo que `C-10` declara cada reparación.
- Cuando la detección no es limpia, **no se ofrece nada**: se declara el desfase
  y se para.

### 4.1 · Qué es un desfase «limpio»

Tres condiciones, todas medibles, y las tres tienen que darse:

1. **Explica casi todo**: la traslación ganadora mete dentro de su recinto a
   ≥ 95% de los recintos mirados. (El umbral de detección, para declarar que
   hay algo raro, sigue siendo el 80% ya existente.)
2. **No tiene rival**: ninguna otra traslación *distinta* —a más de una unidad
   de dibujo de la ganadora— explica una fracción comparable. Dos traslaciones
   que explican lo mismo son dos hipótesis, y elegir entre ellas sería adivinar.
3. **La detección ha llegado a verificarse**: hay una ganadora, no un empate
   entre votos sin verificar.

Sobre `plantasimple.dxf`, medido: la ganadora explica **199 de 200** y no hay
ninguna competidora. Es el caso limpio.

## 5. Casos de uso

1. **Plano normal** (los cinco de referencia): no hay desfase, no se detecta
   nada, no se pregunta nada. Una medición, como hoy.
2. **`plantasimple`**: se mide, el servidor declara el desfase limpio, el
   comando pregunta, él dice `Si`, **se vuelve a medir** con los rótulos
   alineados, y el acta lo declara.
3. **Dice que `No`** (por defecto): se sigue con la medición que ya se hizo, sin
   nombres, y el aviso queda. No se mide dos veces.
4. **Desfase no limpio**: se declara y no se ofrece. Él decide qué hacer con su
   plano.

## 6. Casos límite

- **Pide alinear y no hay desfase limpio** → no se alinea, y se dice por qué. El
  parámetro es una petición, no una orden.
- **Alinea y sigue sin haber viviendas con total** → puede pasar: el desfase era
  sólo uno de los motivos. El acta lo dirá igual.
- **Dos POST por medición**: sólo cuando hay desfase Y él dice que sí. El camino
  normal sigue siendo una sola llamada.

## 7. Flujo del usuario

```
ARCHMUSE  ->  mide  ->  «los rótulos de este plano están 50,00 unidades
                         por debajo de los recintos: 206 recintos y ninguno
                         con nombre.
                         ¿Los alineo SÓLO para esta medición? Tu dibujo no
                         se toca. [Si/No] <No>
                         Si esto no es intencionado, un DESPLAZA de 0,-50 en
                         tu AutoCAD lo arregla para siempre y no tendré que
                         preguntártelo más.»
          Si  ->  vuelve a medir alineado  ->  el acta lo declara
          No  ->  sigue con lo medido, sin nombres
```

## 8. Criterios de aceptación

1. Sin `alinear_rotulos`, el resultado de **todos** los planos es idéntico al de
   hoy. Bit a bit en los cinco de referencia.
2. Con `alinear_rotulos` y desfase limpio, `plantasimple` publica viviendas con
   total.
3. Con `alinear_rotulos` y desfase **no** limpio, no se aplica nada y se dice.
4. El acta declara la corrección con `dx`/`dy` cuando se aplica.
5. **El DXF del disco no se modifica nunca.** Comprobado por hash del fichero
   antes y después de una medición alineada.
6. El comando **nunca** alinea sin un `Si` explícito, y el valor por defecto de
   la pregunta es `No`.
7. El mensaje incluye la recomendación del `DESPLAZA` con la cifra correcta y el
   signo correcto.

## 9. Riesgos

- **El de verdad: que esto se convierta en «ArchMuse arregla planos».** Mitigado
  por §14.2, que enumera lo que este PRD no autoriza.
- **Medir dos veces** cuesta el doble de tiempo en el caso que lo necesita
  (~9 s + ~9 s en `plantasimple`). Se avisa antes de volver a medir.
- **Un falso limpio**: una traslación que encaja por casualidad. Mitigado por el
  umbral del 95% y por la prueba de rival; y aun así se pregunta, que es la
  razón por la que la condición de Pablo de preguntar siempre no es redundante
  con el detector.

## 10. Impacto sobre módulos existentes

- `analyzer/parser.py` — `DesplazamientoDeRotulos` gana `limpio`;
  `extract_labels`/`extract_unit_labels` aceptan un desplazamiento;
  `leer_plano` gana `alinear_rotulos`; `PlanoLeido` gana `rotulos_alineados`.
- `analyzer/medicion.py`, `agente/skills/medicion.py`, `agente/herramientas/
  plano.py` — la corrección viaja al acta, mismo camino que `C-10`.
- `app.py` — el endpoint acepta `alinear_rotulos` y publica el desfase detectado.
- `autocad/archmuse.lsp` — la pregunta, el segundo POST y el mensaje.

## 11. Plan de implementación

| | Tarea |
|---|---|
| A1 | `limpio` en el detector: umbral del 95% y prueba de rival. Tests |
| A2 | Desplazamiento en memoria: `extract_labels` / `extract_unit_labels` / `leer_plano(alinear_rotulos=)` |
| A3 | Que la corrección llegue al acta y a la respuesta |
| A4 | El `.lsp`: preguntar, volver a medir, y la recomendación del `DESPLAZA` |
| A5 | Regresión: los cinco de referencia sin cambios, y el hash del DXF |

## 12. Plan de pruebas

Lo de §8. El que más importa es el 5 —el hash del fichero— porque es la promesa
que da permiso a todo lo demás.

## 13. Métricas

Cuántas veces se ofrece y cuántas dice que sí. Si ofrece mucho y acepta poco, el
detector está viendo desfases donde no los hay.

## 14. Posibles motivos para NO implementar

**14.1 · El argumento en contra.** Un plano con los rótulos a 50 metros de sus
recintos **está mal dibujado**, y lo que de verdad le sirve al arquitecto es
arreglarlo, no que se lo compensemos cada vez. Hay un riesgo real de que la
opción cómoda impida la corrección buena: si ArchMuse lo apaña siempre, él nunca
lo arregla, y el siguiente programa que abra ese DXF volverá a fallar.

Por eso el mensaje lleva **las dos cosas** y en este orden: primero la salida de
hoy, y detrás la recomendación de arreglarlo de verdad, con el `DESPLAZA`
concreto. Y por eso se pregunta **cada vez** en vez de recordar la respuesta: la
pregunta repetida es, deliberadamente, un incentivo a arreglar el plano.

**14.2 · Lo que este PRD NO autoriza.** Escrito antes de que alguien lo dé por
incluido:

- Mover geometría. Se mueven **rótulos**, y sólo en memoria.
- Escribir en el DXF, ni el del disco ni el materializado.
- Rotar, escalar o deformar nada: **sólo una traslación rígida**.
- Recordar la respuesta entre ejecuciones.
- Aplicarlo por defecto, ni siquiera con una detección perfecta.
- Ofrecerlo cuando la detección no es limpia.

---

**Decisión:** **APROBADO por Pablo el 2026-09-11**, con las condiciones duras de
§0 como parte de la firma.
