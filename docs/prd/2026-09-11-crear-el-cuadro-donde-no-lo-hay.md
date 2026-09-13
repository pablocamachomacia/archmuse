# PRD — Crear el cuadro de superficies donde el plano no lo tiene

**Estado:** **SUSTITUIDO** por `2026-09-12-el-cuadro-propio-de-archmuse.md` · **Fecha:** 2026-09-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** nunca se aprobó

> **Por qué queda sustituido y no borrado (2026-09-12).** Este PRD cubría un
> caso —«no hay cuadro»— y se paró esperando un dato del arquitecto: *¿por qué
> `V5.dxf` no tiene cuadro?* El dato llegó, y resultó ser más ancho que la
> pregunta: **ArchMuse entrega siempre su cuadro, haya uno o no**. Este
> documento pasa a ser el `CU-A` del PRD del 12-sep.
>
> **Lo que sigue siendo bueno de aquí, y se ha llevado al nuevo:** el riesgo de
> dibujar geometría en el plano de un cliente (§9 R-1), la métrica de éxito
> —*que se quede la tabla*— y, sobre todo, la objeción de §14.2: **no existe «el
> formato del estudio»**. El diseño nuevo la disuelve en tres de los cuatro
> casos —se copia el cuadro que tiene delante, no se elige entre sus tres— y en
> el cuarto la resuelve declarando que el formato es de ArchMuse.
>
> **Y una cosa que no envejeció bien y conviene mirar:** aquí se recomendó
> esperar a preguntarle. La espera costó un día de no entregar nada, y la
> respuesta cuando llegó no eligió entre las tres hipótesis: las descartó todas.

> **Por qué es un PRD aparte y no un añadido.** Rellenar el cuadro del arquitecto
> es completar un documento que él ha hecho. **Crear uno es escribir un documento
> nuevo en su plano**, con un formato que alguien ha tenido que decidir. Son dos
> cosas distintas y la segunda es mucho más invasiva: el `2026-09-10` se aprobó
> precisamente porque *«una tabla nueva al lado de la suya no le ahorra el
> trabajo»*. Esto propone justo eso —una tabla nueva— pero **sólo donde no hay
> ninguna**, que es un caso distinto y hay que argumentarlo por separado.
>
> **Adelanto mi recomendación, que está en §14: hoy no.** Y no por el coste, sino
> porque falta un dato que sólo tiene el arquitecto.

---

## 0. El hallazgo que lo motiva, medido

`V5.dxf` se probó con el comando el 2026-09-11 y no rellenó nada. El mensaje fue
el genérico —«si tu cuadro está dibujado con líneas y textos sueltos, ArchMuse
todavía no sabe rellenarlo»— y había que averiguar cuál de los dos casos era.

**Es el caso (a): no hay cuadro.** No está dibujado de otra forma, es que no
existe. Comprobado:

| | `V5.dxf` | `v1plantas.dxf` (control) |
|---|---|---|
| `ACAD_TABLE` en modelspace, layouts y bloques | **0** | 1 |
| `LINE` en modelspace | **0** | 0 |
| Textos que suenen a cuadro | **0** de 29 | los del cuadro |
| Capa `00 CUADROS` | existe, **vacía** | existe, **vacía** |

Los 29 textos de `V5.dxf` son rótulos de estancia (`Salón/cocina`, `Dormitorio
1`…) y códigos de vivienda (`VT1/3`, `VT2/2`, `VT3/3`, `VT22/1`) y nada más. **Un
cuadro dibujado a mano necesitaría líneas, y no hay ni una.**

La capa `00 CUADROS` no dice nada en ninguna dirección: existe y está vacía **en
los dos ficheros**, y el `ACAD_TABLE` de `v1plantas.dxf` está en la capa `0`.

**Y `V5.dxf` es el plano que mejor mide de todo el lote**: 22 recintos, tres
viviendas completas (`VT1/3`, `VT2/2`, `VT3/3`), las tres publicando superficie.
Es el único donde ArchMuse tiene todo lo que necesita y no tiene dónde ponerlo.

## 1. Problema que resuelve

El arquitecto tiene un plano medido de tres viviendas y ninguna tabla donde
llevar esas cifras. Hoy el comando se para y le dice que no sabe hacer nada, que
es honesto pero inútil: ArchMuse **ha medido bien** y el trabajo se pierde.

Las alternativas que ya tiene son dos y las dos son peores de lo que parecen:
dibujar el cuadro a mano y volver a ejecutar el comando (dos pasos, y el primero
es el trabajo), o irse a la vía web y llevarse el PDF (que no le deja el dato en
el plano, que es donde lo quiere).

## 2. Usuario afectado

El mismo arquitecto, con el plano que está **antes** de tener cuadro: la planta
recién distribuida, antes de preparar la documentación de visado. Es un momento
del trabajo distinto del que cubre el PRD del 10-sep —allí el cuadro ya existe y
falta rellenarlo— y posiblemente anterior.

**Eso es exactamente lo que hay que confirmar antes de construir nada** (§14).

## 3. Objetivo de negocio

Si se resuelve, ArchMuse deja de depender de que el plano venga preparado. Hoy la
capacidad sólo funciona sobre planos que ya tienen la tabla, y de los cinco
planos reales **sólo tres la tienen** — el 60%. `plantasimple.dxf` tiene 25
cuadros y `V5.dxf` ninguno.

El riesgo de negocio es el contrario y no es pequeño: **un producto que escribe
tablas en planos ajenos se equivoca de sitio, de tamaño o de formato mucho más
fácilmente que uno que rellena huecos existentes** — y de eso ya hemos tenido
tres muestras en dos días, todas con la marca de borrador, que es un solo MTEXT.

## 4. Objetivo técnico

1. El comando reconoce que **no hay cuadro** y lo distingue de «hay uno y no lo
   entiendo». Hoy dice lo segundo cuando es lo primero.
2. Ofrece crearlo, **preguntando**, nunca por iniciativa propia.
3. El cuadro creado usa **el formato de los cuadros que el estudio ya tiene**, no
   uno inventado.
4. Se inserta donde el arquitecto diga, y **no toca nada de lo dibujado**.
5. Lleva la marca `C3` con las mismas reglas de siempre.

## 5. Casos de uso

**CU-1 · Una planta con varias viviendas y sin cuadro.** `V5.dxf`: tres
viviendas medidas. ¿Un cuadro por vivienda, tres cuadros, o uno con tres
columnas? **No se sabe, y es la pregunta de §14.**

**CU-2 · Una vivienda sola y sin cuadro.** El caso simple, si aparece.

**CU-3 · Hay cuadro pero ArchMuse no lo reconoce.** *No es este PRD.* Aquí NO se
crea nada: crear uno al lado del suyo sería duplicarlo, que es el error que el
PRD del 10-sep existe para no cometer. Lo que hay que hacer es aprender a leer el
suyo, y para eso hace falta un ejemplar — que hoy no tenemos.

## 6. Casos límite

- **Un cuadro que ArchMuse no ve por un fallo suyo**, y crea otro encima. Es el
  peor caso de todos y el que justifica que la creación **siempre** pregunte.
- **Dónde ponerlo**: un plano de 22 recintos tiene sitio libre en muchas partes,
  y ninguna es obviamente la buena. Que lo señale el arquitecto.
- **A qué escala**: `V5.dxf` está en metros y el cuadro de los otros se escribe a
  0,125 de altura de texto. Habría que derivarlo del plano, con el mismo cuidado
  que costó tres intentos en la marca de borrador.
- **Varias viviendas**: ver CU-1.

## 7. Flujo del usuario

1. `ARCHMUSE` sobre un plano sin cuadro.
2. El comando mide y dice: *«He medido 3 viviendas y este plano no tiene cuadro
   de superficies. ¿Quieres que te lo dibuje? [Si/No]»*, enseñando las cifras
   **antes**.
3. Si dice que sí, pide punto de inserción.
4. Dibuja el cuadro con el formato del estudio, ya relleno, con su marca.
5. Un `UNDO` lo quita entero.

## 8. Criterios de aceptación

- [ ] Sobre `V5.dxf`, el comando distingue «no hay cuadro» de «no lo entiendo».
- [ ] No se crea nada sin que el arquitecto diga que sí.
- [ ] El cuadro creado tiene **las mismas filas y la misma redacción** que los
      que él ya usa, no una aproximación.
- [ ] Ninguna entidad previa del plano se modifica.
- [ ] Lleva la marca `C3` y un solo `UNDO` lo deshace.
- [ ] Si ya había un cuadro, **no se crea** aunque no se haya podido rellenar.

## 9. Riesgos

**R-1 · Escribir geometría nueva en el plano de un cliente.** Todo lo que hemos
hecho hasta hoy rellena huecos o añade un MTEXT en su capa. Esto **dibuja una
tabla**. La marca de borrador —un solo texto— costó tres intentos: encima del
cuadro, al triple de tamaño, y reventando a mitad. Una tabla tiene sitio, tamaño,
anchos de columna, alturas de fila, estilo de texto y bordes.

**R-2 · Duplicar el cuadro del arquitecto.** Si ArchMuse no reconoce uno que sí
está, crea otro y el plano queda con dos cuadros que dicen cosas distintas. Es
peor que no hacer nada y sólo lo evita preguntar siempre.

**R-3 · No hay UN formato del estudio.** Ver §14.2: sus tres cuadros no son
iguales entre sí.

**R-4 · Compite con `plantasimple.dxf`**, que es el siguiente en el orden de
trabajo y afecta a un plano de proyecto completo con 25 cuadros ya dibujados.

## 10. Impacto sobre módulos existentes

| Fichero | Qué le pasa |
|---|---|
| `autocad/archmuse.lsp` | **Vuelve `vla-AddTable`**, que se retiró el 2026-09-10 y hoy tiene un test que lo prohíbe. Ese test habría que acotarlo, no borrarlo |
| `analyzer/reparto_cuadro.py` | Nada. El reparto es el mismo; lo que cambia es que las celdas no existen todavía |
| `analyzer/cuadro_superficies.py` | Necesita una **plantilla**: qué filas y con qué texto |
| El endpoint | Devolvería además la plantilla del cuadro a crear |

## 11. Plan de implementación

Sin estimar a propósito: **§14 recomienda no hacerlo todavía**, y estimar tareas
de algo que no se ha decidido construir invita a construirlo.

Lo que sí está claro es el orden si se aprueba: (1) distinguir «no hay cuadro» de
«no lo entiendo» —que es útil en cualquier caso y es media hora—, (2) la
plantilla, derivada de sus cuadros, (3) preguntar y crear, (4) el caso de varias
viviendas.

**El punto (1) se puede hacer ya y por separado**, sin comprometer nada de lo
demás: hoy el mensaje de `V5.dxf` dice algo que no es cierto.

## 12. Plan de pruebas

Lo mismo que el PRD del 10-sep, más: que un plano que **sí** tiene cuadro nunca
reciba uno nuevo, con los tres ficheros del estudio como control.

## 13. Métricas de éxito

La única que vale: **que el arquitecto se quede el cuadro que ArchMuse le
dibuje**, en vez de borrarlo y hacer el suyo. Si lo borra, el formato está mal y
la capacidad no sirve por muy bien que funcione.

## 14. Motivos para NO implementarlo — y mi recomendación

### 14.1 Recomendación: hoy no, y no por el coste

Falta un dato que no está en ningún fichero y que sólo tiene el arquitecto:
**¿por qué `V5.dxf` no tiene cuadro?**

Las tres respuestas posibles llevan a tres productos distintos:

- **«Porque aún no lo he hecho»** → este PRD tiene sentido y hay que hacerlo.
- **«Porque el cuadro de esa planta está en otro plano»** → no falta nada, y
  crear uno le mete en el plano un documento duplicado que tendrá que borrar. Es
  la hipótesis que más encaja con lo que vemos: `V5.dxf` es una **planta con tres
  viviendas** y los tres ficheros que sí tienen cuadro son **viviendas tipo**.
  Puede que el cuadro viva donde vive la vivienda tipo, no donde vive la planta.
- **«Porque ese plano no lleva cuadro nunca»** → no se construye nada.

**Construir antes de saberlo es apostar a una de tres.** Y la pregunta es una
sola frase.

### 14.2 Y hay un problema de fondo: no existe «el formato del estudio»

El encargo dice, con razón, que el formato tendría que salir de los cuadros que
él ya usa. **Se han mirado los tres, y no son el mismo cuadro:**

| | `v1plantas.dxf` | `v2s.dxf` | `v3s.dxf` |
|---|---|---|---|
| Campos | **17** | **18** | **18** |
| `S. CONSTRUIDA EXTERIOR` | no está | sí | sí |
| Superficie construida cerrada | `S. CONSTRUIDA C.` | `S. CONSTRUIDA CERRADA` | `S. CONSTRUIDA CERRADA.` |
| Total interior | `TOTAL SUP. INTERIOR (m2)` | `TOTAL SUP.UTIL INTERIOR (m2)` | idem |
| Filas declaradas | 14 | 33 | 33 |

Tres versiones del mismo proyecto y tres cuadros distintos: uno con 17 campos y
dos con 18, y la misma fila escrita de tres maneras —con punto, sin punto, con
abreviatura—. **Copiar uno es elegir por él cuál de sus tres formatos es el
bueno**, que es precisamente el tipo de decisión que `C-1`, `C-2` y `C-8` dicen
que ArchMuse no toma.

Hay una salida razonable si esto se aprueba: **preguntarle de cuál de sus planos
copiar el formato**, o dejar que señale un cuadro existente como modelo. Pero eso
también hay que decidirlo, y es otra pregunta para él.

### 14.3 Lo que sí conviene hacer ya, cueste lo que cueste poco

**Corregir el mensaje de `V5.dxf`.** Hoy dice:

> «Si tu cuadro está dibujado con líneas y textos sueltos en vez de con una tabla
> de AutoCAD, ArchMuse todavía no sabe rellenarlo.»

Y en `V5.dxf` **eso no es verdad**: no hay cuadro de ninguna clase. El mensaje
manda a buscar un cuadro que no existe, igual que el de las celdas mandó a mirar
`ssget` cuando el problema era el servidor. Distinguir los dos casos es barato —
mirar si hay `ACAD_TABLE` en el dibujo— y **es independiente de que este PRD se
apruebe o no**.

Propongo hacerlo aparte, como corrección, y que diga lo que de verdad pasa: que
ha medido 3 viviendas, que este plano no tiene cuadro, y qué puede hacer él.
