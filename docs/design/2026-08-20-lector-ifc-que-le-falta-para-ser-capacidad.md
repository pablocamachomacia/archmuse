# `bim/lector_ifc.py` — qué le falta para ser una capacidad real y registrable

**No es un PRD ni una propuesta de registro.** Es el documento que pide
explícitamente el paso 3 del roadmap de hoy (2026-08-20): decir con precisión
qué falta, sin registrar la capacidad ni tocar `agente/registro.py` — eso
sigue bloqueado por `C4`/`D-12`, sin excepción, y lo decide Pablo cuando
`OP-5`/`BIM-1` se aborden de verdad. `bim.inventario_de_ifc` sigue retirada
del registro (`CAPACIDADES = ()` en `agente/herramientas/bim.py`, decisión de
Pablo del 2026-08-19) — nada de lo de abajo la restaura.

## 0. Punto de partida, verificado hoy, no asumido

`bim/lector_ifc.py` funciona contra IFC reales de terceros, no solo contra el
round-trip sintético de `analyzer/ifc_export.py` — verificado con tres
ficheros de `buildingSMART/Sample-Test-Files` (ver
`tests/fixtures/ifc_real/README.md`): un IFC exportado por SketchUp, uno de
disciplina estructural de otro software, y un fichero de referencia ISO con
una ventana real. Los tres se leen sin excepción, con la corrección de
unidades aplicada (`_Escalas`/`_escalas_unidad`, ver el docstring del módulo)
y sin dejar invisibles las clases de elemento que no estaban en la lista fija
anterior.

Esto responde la pregunta de `OP-5` de forma distinta a como estaba escrita en
el backlog: no es que "la lectura ya funciona" en abstracto — ahora está
verificado que funciona contra ficheros que ArchMuse no ha escrito, con al
menos un bug de unidades real corregido en el camino. Eso no cambia el
veredicto de `OP-5` (ver §4), pero sí baja el riesgo de la premisa sobre la
que ese veredicto se apoya.

## 1. Lo que hoy lee, en dos frases

Un inventario declarativo: esquema, proyecto, plantas (con elevación),
espacios (con superficie/volumen si el modelo los declara), aberturas
—puertas/ventanas— (con ancho/alto si los declara), sitio (coordenadas
geográficas si las declara), y un recuento completo de qué clases de elemento
existen de verdad en el modelo. Nunca calcula nada de la geometría: todo sale
como `None` con motivo si el fichero no lo declara.

## 2. Lo que le falta para `BIM-1` (importador a atributos con procedencia)

`BIM-1` (`docs/AGENTE_BACKLOG.md` §7, `P2`, `PENDIENTE`, PRD: sí, depende de
`TL-3`) pide que lo que este módulo lee entre al grafo de atributos
(`agente/contexto.py`) como `Atributo` con `origen=observado` y la entidad
IFC concreta como procedencia. Concretamente falta:

1. **Un traductor `InventarioIFC` → `Atributo`**, fuera de `bim/` (que no
   importa `agente/` por regla de frontera, ver `BIM-3` más abajo). Cada
   `EspacioIFC.superficie_m2`, cada `AberturaIFC.ancho_m`, etc. tendría que
   convertirse en un `Atributo` cuya procedencia cite el `GlobalId` concreto
   del `IfcSpace`/`IfcDoor` del que salió — el módulo ya expone
   `identificador` (el `GlobalId`) en las cuatro entidades nuevas
   precisamente porque es el dato que ese traductor va a necesitar.
2. **Una `Skill` que invoque esa Capacidad** — sin ella, registrar
   `bim.inventario_de_ifc` de nuevo repite exactamente el error que motivó su
   retirada el 2026-08-19 (capacidad sin Skill que la use, sin entregable que
   la consuma). `D-12`/`C4` lo exigen, no es una preferencia de estilo.
3. **Decisión de si `_Escalas`/las cuatro entidades nuevas viajan tal cual al
   `Atributo`, o si el traductor las aplana.** No se decide aquí: es diseño
   del propio `BIM-1`, no de este módulo.

## 3. Lo que le falta para `BIM-2` (contraste IFC ↔ declarado ↔ DXF)

`BIM-2` (`P2`, `PENDIENTE`, PRD: sí, depende de `BIM-1`) pide detectar
discrepancias entre el modelo IFC, lo que declaró el cliente, y el DXF, **sin
elegir una fuente**. Esto **no puede vivir dentro de `bim/lector_ifc.py`**, y
conviene decirlo con la misma claridad con la que el propio módulo defiende
su filosofía de "no calcular lo que el fichero no dice":

- El módulo lee **una** fuente. Comparar tres fuentes es una capacidad
  distinta, con su propio criterio de umbral de discrepancia y su propia
  forma de presentar un hallazgo con tres cifras y tres orígenes — el mismo
  patrón que `analyzer/circulation.py`/`spatial_quality.py` ya usan para no
  mezclar cálculo normativo con heurística de diseño.
- Necesita, como mínimo: (a) el resultado ya existente de
  `superficies.medicion_de_planta` (DXF) con su propia procedencia, (b) lo
  que este módulo lee del IFC, (c) el dato declarado por el cliente
  (`solar`/`proyecto` en el flujo de `/api/generar`, o el pliego), y (d) un
  umbral configurable de discrepancia — ninguno de los tres primeros datos
  falta hoy en el repo; lo que falta es el módulo que los cruza y el criterio
  de umbral, que es trabajo de diseño, no de lectura.

## 4. El veredicto de `OP-5` en el backlog sigue siendo válido, y hay que decirlo

`docs/AGENTE_BACKLOG.md` §OP-5 dice: *"la lectura ya funciona. Lo que falta
no es leer IFC: es tener con qué contrastarlo, y eso es el grafo portante y
el corpus. Adelantarlo produce un visor de propiedades, que ya tienen
todos."* Esta sesión amplía la lectura (§1) precisamente porque Pablo lo
pidió explícitamente hoy como paso 3 del roadmap, con límites duros que
impiden tocar exactamente lo que el veredicto dice que falta de verdad
(`C4`/registro, corpus normativo). Eso es coherente, no una contradicción: se
ha hecho el trabajo de robustez (`BIM-4`) que no depende de esas dos piezas,
y se ha dejado explícitamente sin tocar lo que sí depende de ellas. El
veredicto de `OP-5` no cambia por esta sesión — sigue sin tener con qué
contrastar el inventario, que es la parte cara y de verdadero valor
diferencial (`BIM-2`, §3).

## 5. Robustez (`BIM-4`) que sigue sin probar, honestamente

No se ha llegado a probar dentro de las 2 horas de esta sesión:

- **IFC2X3**, el esquema anterior a IFC4, todavía muy usado en software real
  (Revit lo exporta por defecto en muchas configuraciones antiguas). El
  módulo no distingue esquema en su código (usa `by_type`/`get_psets`
  genéricos, que funcionan en ambos), pero no se ha verificado contra un
  fichero IFC2X3 real — solo contra IFC4.
- **Ficheros grandes** (decenas/cientos de MB, un edificio completo con
  miles de elementos) — límite de tamaño/memoria, mencionado explícitamente
  en `BIM-4` del backlog. Los tres ficheros de prueba de hoy son pequeños
  (12KB-297KB).
- **`IfcSpace` sin ninguna relación de planta** (ni `Decomposes` ni
  `ContainedInStructure`) — el código ya devuelve `None` en ese caso
  (`_planta_de`), pero no se ha verificado contra un fichero real que
  presente ese caso; solo contra la lógica en abstracto.
- **Elementos estructurales con dimensiones/material declarados** — esta
  ampliación añadió ancho/alto de puertas y ventanas (atributos directos del
  propio esquema), pero no equivalente para muros/columnas/vigas/losas
  (que no tienen un atributo de dimensión tan directo — su geometría suele
  vivir en la representación 3D, exactamente el tipo de dato que este módulo
  decide no teselar). Si en el futuro se necesitan datos declarados de
  estructura (p. ej. `LoadBearing` de `Pset_WallCommon`, o el material vía
  `IfcMaterial`), es una ampliación futura del mismo patrón "declarado o
  `None` con motivo", no calculada de la geometría.

## 6. Resumen para decidir

No hay nada que decidir hoy: `BIM-1`/`BIM-2` siguen `PENDIENTE`, con PRD
propio pendiente de escribir cuando Pablo los aborde, y `bim.inventario_de_ifc`
sigue fuera del registro. Este documento existe para que, cuando llegue ese
momento, no haya que re-derivar desde cero qué falta — y para que quede
constancia de que la ampliación de hoy (unidades, inventario completo de
clases, aberturas, plantas, sitio) es trabajo de `BIM-4` (robustez), no un
adelanto encubierto de `BIM-1`/`BIM-2`.
