# Resumen de cierre — 2026-08-20

Punto de partida para mañana. No es un PRD ni un informe de auditoría completo
— es el resumen de una sesión, para no tener que reconstruir el día leyendo
`PROGRESS.md` entero. Todo lo que cita una fecha/commit está verificado contra
el repo real, no recordado de memoria.

---

## 1. Qué se cerró de verdad hoy

- **Selector de modo (dropdown) arreglado y confirmado por ti.** El fallo
  real: seleccionar "Revisar coherencia" actualizaba la etiqueta del botón
  pero no llamaba a `convActualizarSugerencia()` — el fantasma de sugerencia
  se quedaba congelado con el ejemplo del modo anterior. Arreglado junto con
  dos síntomas del mismo origen (texto por defecto del fantasma, prioridad de
  sugerencias al escribir). Verificado en navegador con clics reales, 7/7
  comprobaciones en verde. Commit `6f7ad75` (en `origin`).
- **Fase A del PRD de procedencia de parcela.** `analyzer/sitio.py`/
  `storage.py`/`app.py`/frontend: procedencia estructurada (fuente + fecha de
  consulta) adjunta a los datos de Catastro, con las 3 notas que pediste
  incorporadas. Testeada (`test_checklist_campo.py` nuevo, `test_sitio.py`
  ampliado, `test_analizar_sitio_procedencia.py` nuevo end-to-end), subida a
  GitHub. Commit `681b358` (en `origin`). Su cabecera se corrigió hoy mismo
  (seguía en `Borrador`/`_pendiente_` pese a estar implementada) — ver §2,
  sigue sin commitear junto con el resto de correcciones documentales.
- **CI real en verde, no solo "creído en verde".** El workflow de GitHub
  Actions llevaba desde el 19-ago en rojo en cada push sin que nadie lo
  hubiera mirado (el backlog lo daba por "sin ejecutar", que era falso).
  Causa real: `test_entorno_3d.py` no mockeaba una llamada de red real en 3
  de sus 4 secciones y golpeaba Catastro de verdad en CI. Arreglado en las
  tres, confirmado con `gh run watch`: **2 fallos, los mismos guardianes de
  C4 de siempre, cero señal espuria nueva.** Commit `7491519` (en `origin`).
- **PoC de lectura BIM (`bim/lector_ifc.py`) ampliado y verificado contra IFC
  reales.** No solo el round-trip sintético de `analyzer/ifc_export.py`: 3
  IFC de terceros (`tests/fixtures/ifc_real/`). Corregido un bug real de
  unidades (longitud del proyecto en milímetros, pero área/volumen en
  unidades SI independientes ya en m²/m³ — mi primer intento de arreglo
  también estaba mal, corregido antes de que llegara a ningún test). Añadida
  lectura de plantas con elevación, puertas/ventanas con dimensiones
  declaradas, sitio con coordenadas geográficas declaradas, e inventario de
  clases completo (la lista fija anterior dejaba invisible casi la mitad de
  los elementos de un IFC real). Suite completa: 1073 passed, 2 failed (los
  mismos guardianes de C4). Commits `8b94e8e` + `b0a74ca` — **sin push**, ver
  §2.

## 2. Qué queda pendiente de tu revisión — nada más se ejecuta hasta entonces

### PRDs nuevos, sin aprobar, sin commitear

- `docs/prd/2026-08-20-accesibilidad-geometrica-itinerarios.md` (OP-17) —
  Borrador. Aviso ya incluido en el propio PRD: de las tres cifras que
  promete OP-17 en el backlog, dos (anchos de hueco de puerta, pendientes de
  rampa) no son calculables hoy sin un modelo de carpintería que el repo no
  tiene.
- `docs/prd/2026-08-20-retranqueos-vs-parcela-real.md` (OP-18) — Borrador.
  Pregunta abierta sin decidir en el propio PRD (§6): no existe hoy
  transformación entre el sistema de referencia de Catastro (lon/lat) y las
  coordenadas locales del DXF — sin resolver eso no hay estimación de horas
  fiable.

### Cabeceras de PRD corregidas hoy (descuidos de cierre encontrados en auditoría), también sin commitear

- `docs/prd/2026-08-15-analisis-de-sitio.md` — cerrado como Aprobado hoy
  (confirmación tardía: llevaba días con "implícito, a confirmar" mientras
  varios PRDs posteriores ya construían sobre él como si estuviera firme).
- `docs/prd/2026-08-19-escritura-protegida-del-dxf-del-cliente.md` — párrafo
  de cierre actualizado (ya estaba Aprobado en la cabecera; el párrafo final
  seguía diciendo "decisión pendiente").
- `docs/prd/2026-08-19-planificador-tipado.md` — igual, con una sub-pregunta
  (¿el bucle de `nucleo.py` se conserva indefinidamente o se le pone fecha?)
  dejada explícitamente sin decidir, no encontrada resuelta en ningún sitio.
- `docs/prd/2026-08-19-skill-del-cuadro-de-superficies.md` — igual.
- `docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md` — cabecera
  corregida de `Borrador`/`_pendiente_` a `Aprobado e implementado`.

### Commits locales hechos, sin push

En la rama `agente/nucleo-agentico`, **2 commits por delante de `origin`**:

1. `8b94e8e` — ampliación de `bim/lector_ifc.py` (corrección de unidades,
   inventario de clases completo, aberturas, plantas, sitio) + fixtures +
   tests + el documento de qué falta para BIM-1/BIM-2.
2. `b0a74ca` — entrada de cierre de esa misma sesión en `PROGRESS.md`.

### Tensión encontrada, no resuelta por mi cuenta: la ampliación de BIM de hoy vs. el veredicto antiguo de OP-5

`docs/AGENTE_BACKLOG.md` §OP-5 dice, textualmente: *"la lectura ya funciona
(`bim/lector_ifc.py`). Lo que falta no es leer IFC: es tener con qué
contrastarlo, y eso es el grafo portante y el corpus. Adelantarlo produce un
visor de propiedades, que ya tienen todos."* — por eso OP-5 sigue en V2, no
antes.

Hoy se amplió esa misma lectura (paso 3 del roadmap, que tú pediste
explícitamente) con límites que impedían tocar exactamente lo que el
veredicto dice que falta de verdad (C4/registro, y con qué contrastar el
inventario). No es una contradicción — es trabajo de robustez (`BIM-4`) que
no dependía de esas dos piezas — pero el veredicto de `OP-5` **no ha
cambiado**: sigue sin haber con qué contrastar el inventario (`BIM-2`), que
es la parte de valor diferencial real. Detalle completo en
`docs/design/2026-08-20-lector-ifc-que-le-falta-para-ser-capacidad.md` §4.
No decido aquí si esto debe mover la prioridad de `BIM-1`/`BIM-2` — es tu
llamada, con el dato nuevo de que la lectura ya está verificada contra
software real, no solo contra el propio exportador de ArchMuse.

## 3. Qué está bloqueado, y de quién depende

| Bloqueo | Depende de |
|---|---|
| `D-12` — techo de `C4` (registro en 13 capacidades, tope en 12) | **Tuya.** Decisión de producto; la propuesta de reformulación ya está escrita en `docs/design/2026-08-19-revision-formal-de-C4.md`, pendiente de que la leas |
| `NOR-1` — contratar al curador de corpus normativo | **Tuya.** Es contratación, no código; no avanza por sí sola |
| Corpus normativo CTE | Bloqueado por `NOR-1` — no empieza sin esa persona, sin excepción |
| `BIM-1` (importador IFC → grafo de atributos, `agente/contexto.py`) | Código, PRD: sí. Sin bloqueo externo — pendiente de que decidas avanzarlo |
| `BIM-2` (contraste IFC ↔ declarado ↔ DXF) | Código, PRD: sí, depende de `BIM-1`. Misma situación |
| `OP-17` (accesibilidad geométrica) | PRD escrito hoy, sin aprobar — pendiente de tu lectura |
| `OP-18` (retranqueos vs. parcela real) | PRD escrito hoy, sin aprobar — pendiente de tu lectura, y con una pregunta técnica propia sin decidir (§6 del PRD: sistemas de referencia) |

## 4. La decisión estratégica de hoy

ArchMuse no aspira a ser un copiloto general de arquitectura. La apuesta es
una **capa de verificación fiable — una auditoría de confianza antes de
visado**. Las dos capacidades priorizadas para después de cerrar V1 son
`OP-17` (accesibilidad geométrica: anchos de paso, radios de giro, pendientes
de rampa) y `OP-18` (retranqueos del edificio medido vs. límite real de
parcela) — ambas sobre el mismo motor geométrico ya existente, sin tocar el
corpus normativo (`docs/AGENTE_BACKLOG.md`, decisión de producto del
2026-08-20).

## 5. Una pregunta abierta para mañana

Qué le pregunto al primer lector en la demo, tal como se decidió hoy: **¿esto le
habría evitado algún problema real de visado?**

---

Este documento se queda sin commitear, junto con el resto de lo pendiente de
§2, a la espera de que lo revises todo en bloque mañana.
