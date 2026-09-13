# PRD — El cuadro de ArchMuse es una plantilla fija (y D-13, D-14, D-15)

**Estado:** EN EJECUCIÓN · **Fecha:** 2026-09-13 · **Autor:** ArchMuse (CTO) ·
**Encargo:** Pablo, 2026-09-13, con siete decisiones explícitas. Escrito y
ejecutado sin esperar aprobación por orden suya: *«media hora está bien pagada:
esto deroga un criterio firmado»*.

> **Lo que este PRD deroga.** `C-4` («un `0,00 m²` sólo se escribe sobre una
> medición limpia») queda sustituido por **`D-13`**: *un `0,00 m²` no es nunca
> una superficie válida de estancia*. Y **`C-5`** deja de aplicarse en la vía del
> comando (con filas sacadas del plano no hay huecos que repartir), aunque su
> mecanismo —celda en blanco con motivo compartido— se reutiliza.

---

## 1. Problema que resuelve

Verificado por Pablo en AutoCAD 2027 sobre un plano real el 2026-09-13:

- **D-13 · Escribe cifras que no ha medido.** El cuadro del arquitecto pedía
  `pasillo` y `vestibulo`; el plano no tiene ninguno (ese estudio mete el
  pasillo en el salón). ArchMuse escribió `0,00 m²`. **Origen medido:** tres
  constructores de `CERO_REAL` en `cuadro_superficies.py` (`:377`, `:397`,
  `:449`) y uno en `aplicar_respuestas` (`:1068`); `condicionar_ceros` (`C-4`)
  los deja pasar sobre medición limpia, que era el caso.
- **D-14 · Escala.** Texto varias veces más alto que el edificio, columnas que
  parten las palabras letra a letra. `am:dibujar-cuadro` crea la tabla con fila
  1,0 y columna 14,0 fijas y **no fija la altura de texto** (hereda el estilo).
  *Hipótesis sin medir:* estilo con altura del orden de 4,5 en un plano en
  metros. Sea cual sea la cifra, **el tamaño era criterio y vivía en LISP**.
- **D-15 · La web nunca aplicó `C-4`.** `cuadro_superficies_export.py:153` y
  `:196` llaman a `calcular_relleno_cuadro` sin `condicionar_ceros`: la vía web
  escribía ceros incluso con la medición sucia.
- **Producto.** ArchMuse clonaba las filas del cuadro del arquitecto, y por eso
  heredaba sus filas vacías (`pasillo`) y sus huecos imposibles (`terraza 2`).

## 2. Usuario afectado

El arquitecto que ejecuta `ARCHMUSE` sobre su plano, y quien lo abra meses
después sin la línea de comandos delante.

## 3. Objetivo de negocio

Un cuadro **idéntico en estructura en todos los proyectos** —dos proyectos del
mismo estudio se comparan de un vistazo— en el que **cada cifra es una medición**
y cada hueco lleva su motivo escrito en el plano.

## 4. Objetivo técnico

### 4.1 La plantilla (servidor, `analyzer/plantilla_cuadro.py`, nuevo)

```
CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA
ESPACIOS INTERIORES | SUPERFICIES UTILES INT. | ESPACIOS EXTERIORES | SUPERFICIES UTILES EXT.
<una fila por estancia medida; interiores a la izquierda, exteriores a la derecha>
TOTAL SUP. INTERIOR (m2) | <cifra> | TOTAL SUP. EXTERIOR (m2) | <cifra>
TOTAL S. UTIL(m2)        | <cifra, C-14> (hasta el 2026-09-13: vacía, C-1)
S. CONSTRUIDA C.         | <cifra o vacía>
VIVIENDA TIPO            | <tipo>  | NUMERO UDS:              | (vacía)
```

- **Filas = estancias medidas.** Tres dormitorios, tres filas. Ninguna estancia
  desaparece (`C-6`); ninguna fila sin estancia.
- **Orden fijo por familia**, nunca el del plano (decisión 3 de Pablo):
  interiores `salón/cocina, salón, cocina, pasillo, distribuidor, dormitorio,
  baño, aseo, vestíbulo` y después las no reconocidas; exteriores `terraza,
  balcón, porche, tendedero` y después las no reconocidas. *Decisión mía,
  declarada:* «salón» solo va justo detrás de «salón/cocina». Dentro de una
  familia: por el número del rótulo y después por el rótulo.
- **Familias nuevas:** `salón` (sin cocina), `cocina` (sin salón),
  `distribuidor` separado de `pasillo`, `recibidor` y `hall` dentro de
  `vestíbulo`, `balcón`, `porche`.
- El texto de la fila es **el rótulo del plano**, no el nombre de la familia.

### 4.2 D-13 · Guardián del cero

- **Invariante permanente:** ninguna celda de superficie de ninguna salida
  (plantilla, cuadro clásico de 18 campos, exportación web, PDF) contiene
  `0,00`. `CERO_REAL` sale del catálogo de estados.
- Estancia que existe con geometría no limpia (en un solape): **celda vacía**
  con motivo.
- Superficie que redondea a 0,00: no es una estancia; vacía con motivo.

### 4.3 Motivos: nota al pie, fuera del marco (decisión 2)

La celda queda **vacía**. Debajo de la tabla, fuera de su marco, una nota por
motivo que empieza por el rótulo de la fila o filas a las que se refiere. Dos
celdas con el mismo motivo comparten nota (el mecanismo de `C-5`).

### 4.4 Interior o exterior (decisión 4)

Una familia que ArchMuse no reconoce produce **una pregunta por familia** (tres
trasteros = una pregunta), decidida en el servidor y viajando al `.lsp`, que la
muestra y devuelve la respuesta. Sin respuesta, esas piezas **no tienen fila**:
van a nota al pie y los totales se quedan vacíos (`C-6`).

### 4.5 Filas de cierre (decisión 5)

| Fila | Valor |
|---|---|
| TOTAL SUP. INTERIOR / EXTERIOR | suma de las cifras publicadas de su lado; vacía si hay impedimento (`C-2`) o pieza sin fila (`C-6`) |
| TOTAL S. UTIL(m2) | **`C-14`** (firmado por un arquitecto colegiado, 2026-09-13): útil interior + el menor entre el 50 % de la exterior y el 10 % de la interior; vacía con motivo si una de las dos no se puede afirmar. Hasta ese día, vacía por `C-1` |
| S. CONSTRUIDA C. | **`C-12` FIRMADO** (2026-09-13): la polilínea que el arquitecto rotula «Superficie construida cerrada», de cualquier capa, nunca por color; vacía con motivo si el rótulo no identifica exactamente una. Ver `docs/design/2026-09-08-criterios-firmados-de-medicion.md`. Antes de firmarse salía vacía con su nota |
| VIVIENDA TIPO | el rótulo de la vivienda |
| NUMERO UDS: | vacía: el plano lo declara («8uds.») y eso es `C-8`, sin implementar |

**`C-12` (PROPUESTO, SIN FIRMAR Y DESACTIVADO: el código queda detrás de
`C12_FIRMADO = False`) · La superficie construida cerrada se mide sobre la
envolvente que el plano dibuja.** Si se firmara, se publicaría cuando
existe **exactamente una** polilínea en la capa de recintos, con color propio,
cerrada (con el flag o recuperada por `_esta_cerrada`), válida, que **contiene
todas las piezas interiores de la vivienda y ninguna exterior**. Cero o más de
una: vacía con motivo. **Medido el 2026-09-13:** `v1plantas`/`v2s` 1 de 1
(73,07 m², ACI 10, flag sin poner, rotulada «Superficie construida cerrada» a
0,23 del borde); `ejemplo` **6 de 6**, siempre una sola; `v3s`, `V5`: ninguna
(no está dibujada). Construida/útil entre 1,20 y 1,27 en las siete.

### 4.6 D-14 · Ventana y maquetación (servidor, `analyzer/maquetacion_cuadro.py`, nuevo)

- El comando pide **dos esquinas**. La ventana es declaración (misma lógica que
  `C-8`) y manda.
- **Altura mínima legible** (decisión 6): la del texto del cuadro del arquitecto
  si lo hay; si no, la mediana de la altura de los rótulos de estancia del
  plano. Nada fijo. *Medido:* rótulos 0,125 y cuadro 0,09 en los seis planos.
- El servidor devuelve la tabla resuelta: esquina, altura de texto, alto de
  fila, **ancho de cada columna** y posición de cada nota. La altura es la mayor
  con la que la tabla y sus notas caben en la ventana.
- **Anchos medidos con la fuente real** (`ezdxf.fonts`, `arial.ttf`); el `.lsp`
  crea y aplica el estilo de texto `ARCHMUSE` con esa fuente, para que lo medido
  y lo dibujado sean lo mismo. Ninguna celda es más estrecha que su texto:
  **ninguna palabra se parte, nunca**.
- Si con la altura mínima no cabe: **no se dibuja**, y se dice qué tamaño de
  ventana hace falta.
- Si la ventana pisa un cuadro del arquitecto (el `.lsp` manda sus cajas): no se
  dibuja.

### 4.7 Web (decisión 7)

La web usa **el mismo constructor de plantilla**: la exportación dibuja la
plantilla (líneas y `MTEXT`, porque `ezdxf` no puede crear un `ACAD_TABLE`) en
su propia capa, a la derecha del cuadro del arquitecto, y **deja de escribir
encima de sus celdas**. `C-9` pasa a comparar también el **contenido** de la
tabla por las dos vías.

### 4.8 El agente también dibuja la plantilla (decisión de Pablo, 2026-09-13)

En la primera pasada el agente se quedó con el cálculo clásico de 18 campos.
Pablo lo revocó el mismo día: *«si el agente calcula distinto que el comando y la
web, C-9 vuelve a romperse por un tercer sitio»*. Así que:

- `plano.cuadro_de_superficies` pasa a **2.0.0** y devuelve la misma rejilla que
  el comando y la web (`celdas`), las `filas` de cada pieza medida (también las
  que no tienen fila, con `tiene_fila: false`), las `notas`, los huecos sin
  cifra con su motivo y las preguntas de ámbito. Un DXF sin cuadro del
  arquitecto **ya no es un error**. `obtener_estado_cuadro` se retira.
- `superficies.cuadro_de_vivienda` pasa a **2.0.0**: cruza la suma de las filas
  (interiores y exteriores, porque la útil medida incluye la terraza) contra la
  superficie medida, y comprueba que ningún hueco con nota lleve cifra ni
  ninguna fila diga `0,00`.
- El PDF del cuadro presenta la plantilla y los motivos.
- G11 y el contrato de capacidades se recapturan con este motivo escrito.

## 5. Casos de uso

1. Plano con cuadro del arquitecto: ventana libre → tabla de ArchMuse al lado.
2. Plano sin cuadro (`V5`): altura desde los rótulos.
3. Plano con trastero: una pregunta, respuesta, fila al final de su bloque.
4. Ventana pequeña: se niega y dice el tamaño necesario.
5. Web: descarga del DXF con la plantilla dibujada.

## 6. Casos límite

Vivienda sin exteriores (columna derecha vacía, sin notas). Piezas sin rótulo
(sin familia → pregunta por la familia vacía «(sin rótulo)»: no, va a nota y
bloquea totales, porque no hay familia que preguntar). Cuatro terrazas (cuatro
filas). Ventana dibujada de abajo arriba (se normaliza). Construida con dos
candidatas (vacía con motivo).

## 7. Flujo del usuario

`ARCHMUSE` → capa → medición → pregunta(s) de ámbito si hace falta → resumen →
`Si` → ventana de dos esquinas → tabla + notas + marca de borrador en un solo
`UNDO`.

## 8. Criterios de aceptación

1. Ninguna salida escribe `0,00` (test que reintroduce el fallo y se pone rojo).
2. La plantilla sale igual en estructura para cualquier plano; filas = estancias.
3. Ninguna palabra más ancha que su columna (test sobre la maquetación).
4. Ventana pequeña → negativa con tamaño necesario.
5. `C-9`: mismo contenido de tabla por web y comando.
6. `C-6`: toda pieza en una fila o en una nota.
7. El `.lsp` no contiene ninguna medida de tabla escrita a mano.
8. `UNDO` retira la tabla entera (grupo de deshacer intacto).

## 9. Riesgos

- **La fuente.** Si el AutoCAD del arquitecto sustituye `arial.ttf`, lo medido y
  lo dibujado difieren: margen del 15 % en el ancho. Sin verificar en AutoCAD.
- **Nada del `.lsp` nuevo se ha ejecutado** (`getcorner`, `SetColumnWidth`,
  estilo de texto). Checklist del trial.
- **`C-12` sin firmar.** Implementado y desactivado: la fila sale vacía con nota.
- **La SPA** pinta hoy los 18 campos; cambia su tabla.

## 10. Impacto sobre módulos existentes

`analyzer/cuadro_superficies.py`, `reparto_cuadro.py`, `medicion.py`,
`cuadro_superficies_export.py`, `cuadro_pdf.py`, `geometria_recibida.py`,
`app.py`, `agente/skills/superficies.py`, `static/app.js`,
`autocad/archmuse.lsp` (3.2.0). Nuevos: `plantilla_cuadro.py`,
`maquetacion_cuadro.py`, generador del fixture sintético.

## 11. Plan de implementación

| | Tarea | ≤2 h |
|---|---|---|
| T1 | Fixture sintético con `ACAD_TABLE` inyectado y cabecera limpia | sí |
| T2 | Tests rojos de D-13, D-14, D-15 y plantilla; verlos fallar | sí |
| T3 | D-13/D-15: fuera `CERO_REAL`, guardián en todas las salidas | sí |
| T4 | Familias nuevas y pregunta de ámbito por familia | sí |
| T5 | `plantilla_cuadro.py`: filas, orden, cierre, notas, `C-12` | no (~3 h) |
| T6 | `maquetacion_cuadro.py`: ventana, altura, anchos, negativa | sí |
| T7 | `app.py` + `geometria_recibida.py`: payload y respuesta nuevos | sí |
| T8 | `.lsp` 3.2.0: ventana, pregunta, dibujo con medidas del servidor | sí |
| T9 | Web: exportación y estado con la plantilla; SPA | no (~3 h) |
| T10 | `C-9` del contenido; reintroducir cada fallo; suite | sí |
| T11 | Enmienda de `C-4`, alta de D-13/D-14/D-15/`C-12`; PROGRESS | sí |

## 12. Plan de pruebas

Fixture sintético (salón+cocina, dormitorio 1, dormitorio 2, una terraza, un
trastero; cuadro del arquitecto con `pasillo`, `vestibulo`, `terraza 1/2`):
reproduce la generación de filas, `C-5` en la vía web y la pregunta de ámbito.
Cada guardián se ve fallar reintroduciendo su fallo.

## 13. Métricas de éxito

En el siguiente trial: cero ceros escritos; ninguna palabra partida; el
arquitecto no mueve la tabla a mano para leerla.

## 14. Posibles motivos para NO implementarlo

- **Tamaño.** Toca la web y la SPA, que no son el producto (§0.0 del PRD del
  10-sep). Alternativa descartada por Pablo: dejar la web clonando, que rompe
  `C-9`.
- **`C-12` antes de firma.** Resuelto el mismo día: desactivado hasta que lo
  confirme un arquitecto; activarlo es una constante.
