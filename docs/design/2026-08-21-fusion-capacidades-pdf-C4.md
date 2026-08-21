# Cierre de C4 — fusión de las tres capacidades de PDF

**Fecha:** 2026-08-21 · **Decisión de:** Pablo · **Prompt:** 1.7

---

## 1. La decisión

El registro vuelve bajo el techo `C4 = 12` **por fusión, no subiendo el
techo**. `docs/design/2026-08-19-revision-formal-de-C4.md` dejó la decisión
abierta con el registro en 13; esta es su cierre.

`plano.medicion_en_pdf`, `plano.cuadro_en_pdf` y `plano.informe_de_coherencia`
—las tres capacidades `io` que escriben un PDF a partir de un DXF, una por
cada dominio (medición, cuadro de superficies, coherencia)— se fusionan en
**una sola entrada de registro**: `plano.entregable_en_pdf`, `version 1.0.0`,
`naturaleza io`, con un parámetro obligatorio `tipo`:
`"medicion" | "cuadro" | "coherencia"`.

**Registro: 13 → 11.**

## 2. Fusión de manifiesto, no de código

Las tres implementaciones —`medicion.medicion_en_pdf`, `plano.cuadro_en_pdf`,
`coherencia.escribir_informe`— **no se han tocado**: siguen siendo funciones
Python normales en sus módulos de siempre, con sus guardianes de escritura
intactos (`_destino_seguro`, `_sha256`, `_con_sello_intacto`, verificación del
sha256 del DXF de origen antes y después). Lo único nuevo es
`agente/herramientas/entregables.py`, que añade una función `entregable_en_pdf`
que despacha a las tres según `tipo`, y una entrada `Capacidad` que las
sustituye en el registro.

El manifiesto de la nueva capacidad conserva **todo** lo que las tres
prometían:

- **Procedencia celda a celda / pieza a pieza / hallazgo a hallazgo**, según
  el tipo — está en la descripción.
- **La lista de lo que NO se comprueba**, íntegra dentro de cada PDF —
  la calcula cada implementación original exactamente igual que antes,
  porque el código no ha cambiado.
- **DXF sólo lectura, sha256 verificado antes y después** — universal a los
  tres tipos, en la descripción y en `limitaciones`.
- **Marca de borrador sin opción de quitarla** — universal, en `limitaciones`.
- **Autorización explícita del efecto `escribe_fichero`** — declarado en la
  capacidad fusionada, exigido antes de despachar a cualquiera de los tres.

### Una consecuencia aceptada, no un descuido

`Capacidad.limitaciones` es una tupla estática del manifiesto: no varía según
los argumentos de una invocación concreta. Con la fusión, **toda invocación
de `plano.entregable_en_pdf` —sea cual sea el `tipo`— lista en el acta las
limitaciones de los tres tipos**, no sólo las del que se pidió. Antes de la
fusión, invocar `plano.informe_de_coherencia` sólo mostraba las limitaciones
de coherencia; ahora también aparecen las de medición y cuadro.

Mitigación aplicada: cada limitación que sólo vale para un `tipo` lleva el
prefijo `(tipo=medicion|cuadro|coherencia)` en su propio texto, así que quien
lea el acta ve de inmediato cuáles no aplican a su invocación — no se oculta
la imprecisión, se etiqueta. Lo que **no** se ha hecho es esconder ningún id
interno de capacidad en el texto: `tests/test_acta_legible_coherencia.py`
encontró y rechazó un primer borrador que citaba `plano.coherencia`,
`plano.medicion_de_la_planta` y `plano.cuadro_de_superficies` por su id dentro
de una limitación — se reescribió en castellano llano.

Si esta imprecisión demuestra ser un problema real de producto (un arquitecto
confundido por una limitación que no le aplica), la solución no es deshacer
la fusión: es que `Capacidad.limitaciones` deje de ser estática y se pueda
calcular a partir de los argumentos de la invocación — una ampliación futura
del núcleo (`agente/capacidad.py`), no de este prompt.

## 3. Dónde vive el despacho, y por qué ahí

`agente/herramientas/entregables.py`, no dentro de `plano.py`, `medicion.py`
ni `coherencia.py`. Poner el despacho en cualquiera de los tres habría creado
una dependencia de ese módulo hacia los otros dos que hoy no existe y que
ningún dominio necesita para su propio trabajo — sólo la fusión de catálogo
la necesita. Un módulo nuevo, pequeño, que sólo orquesta, mantiene los tres
módulos de dominio sin acoplar entre sí por un motivo que es puramente de
`C4`, no de arquitectura de dominio.

## 4. Qué se actualizó fuera del registro

- `agente/skills/medicion.py`, `agente/skills/superficies.py`,
  `agente/skills/coherencia.py`: sus `ctx.invocar(...)` y sus tuplas
  `capacidades=(...)` usan el nuevo id y pasan `tipo`.
- Tests que invocaban las capacidades por su id antiguo, vía el registro
  (`registro().buscar(...)`) o vía `.funcion(...)` directo: actualizados al
  nuevo id + `tipo`. Los tests que llaman a la FUNCIÓN Python original
  directamente (`plano.cuadro_en_pdf(origen, destino)`, en
  `tests/test_cuadro_pdf.py`) **no cambian**: esa función sigue existiendo,
  sin registro propio.
- `tests/test_agente_nucleo.py::test_el_registro_se_puebla_por_descubrimiento`
  y `tests/test_agente_plano.py::test_el_registro_sigue_dentro_del_tamano_que_C4_permite`
  (los dos guardianes de C4): en verde, con el registro en 11 y el techo
  intacto en 12.

## 5. `proyecto.ajustar_programa` — nota para no tocarla por inercia

Sigue en el registro, 12ª/11ª posición. **No se fusiona ni se retira aquí.**
Queda marcada para retirada cuando `/mvp` deje de ser una entrada del
producto (Prompt 4 de la secuencia de Fable 5 — decisión de superficie
única, todavía no ejecutado en este repositorio). Retirarla antes de eso
rompería el copiloto de `/mvp` sin que nadie lo haya decidido explícitamente.
Anotado aquí para que ninguna sesión futura la toque por costumbre de
"reducir el registro" sin mirar si `/mvp` sigue viva.

## 6. Terminado

- Registro: **11** capacidades.
- Techo C4: intacto en **12** (no se subió).
- `test_el_registro_se_puebla_por_descubrimiento` y
  `test_el_registro_sigue_dentro_del_tamano_que_C4_permite`: verdes.
- Suite completa: **verde por primera vez en tres días** — cero fallos,
  incluidos los dos que llevaban tres días en rojo.
