# PRD — Memoria justificativa automática (superficies, sin normativa)

**Estado:** Implementado · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-19)

> Paso 2 de `docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`
> — "única pieza del pedido alcanzable dentro de V1, porque ya existen el
> acta y la reconciliación de datos". Este PRD cubre **solo** esa pieza: el
> apartado de superficies de una memoria, derivado 100% de una medición ya
> hecha. No cubre memoria justificativa normativa (paso 4, requiere corpus
> citable) ni detalles/carpintería (pasos 5-6).

---

## 1. Problema que resuelve

Del informe ejecutivo y de la regla de oro de `CLAUDE.md` §1: *«Detectar que
el cuadro de superficies de la memoria no cuadra con los planos antes de
visar, decir exactamente dónde y por cuánto, y generar el informe.»* Las dos
primeras partes ya existen (medición real, acta de procedencia,
`superficies.medicion_de_planta` vía `/api/preguntar`). **La tercera no**: el
acta de hoy (`agente/acta.py` → `analyzer/acta_legible.py`) es una pantalla
de verificación, pensada para que el arquitecto compruebe qué se midió y qué
no — no un documento que se pueda incorporar a un expediente de visado. El
arquitecto sigue redactando a mano el apartado de superficies de su memoria,
exactamente el paso donde hoy se cuela la discrepancia que el resto del
producto ya sabe detectar.

Distinto del `/api/informe-pdf` que ya existe: ese informe sale de
`analyzer/evaluator.py` (hallazgos de calidad arquitectónica, con umbrales
sin corpus citado — ver `docs/AGENTE_BACKLOG.md` §13.7). Este documento sale
del acta de una Skill real (`agente/acta.py::Acta`), que nunca ha tenido
ese problema porque nunca ha afirmado nada normativo.

## 2. Usuario afectado

El mismo arquitecto que ya usa la conversación (`/mvp`, `/api/preguntar`)
para medir una planta — en el momento de preparar el expediente de visado,
inmediatamente después de ver un acta que le convence.

## 3. Objetivo de negocio

Cierra el ciclo medir → detectar → **entregar** que es el argumento de venta
completo de la V1 (§1 de `CLAUDE.md`). Sin esto, ArchMuse demuestra que sabe
algo pero no deja nada en la mano del arquitecto — la demo se queda en «mira
qué bien mide», no llega a «esto me ahorró la tarde», que es el criterio de
éxito real (mismo criterio que ya midió `docs/design/2026-08-19-valor-comercial-de-las-skills.md`
para la Skill de coherencia).

## 4. Objetivo técnico

Dada un `Acta` ya levantada por una Skill real (hoy, la única:
`superficies.medicion_de_planta`), producir un documento descargable que:

- Reproduce en prosa profesional **exactamente** lo que el acta ya contiene
  (`datos`, `pasos`, `no_comprobado`) — cero cálculo nuevo, cero cifra que no
  estuviera ya en el acta.
- Lleva siempre, íntegra y en un anexo, la procedencia de cada cifra
  (`fuente` = `capacidad@version` o `skill@version`, tal como ya la lleva el
  acta) y el sello (`Acta.sello`).
- Lleva siempre la sección "Qué no se ha comprobado" — nunca opcional, nunca
  resumida.
- Lleva la leyenda de borrador ya estampada (`agente/acta.py::LEYENDA_BORRADOR`,
  la misma que ya usan los PDF de `analyzer/marca_borrador.py`) — este
  documento es un borrador de apoyo, no sustituye el juicio ni la firma del
  arquitecto colegiado.
- **No contiene ninguna afirmación normativa.** Nada de "cumple el CTE",
  "según el DB-SUA", ni un porcentaje de cumplimiento — el corpus citable
  (paso 4 del roadmap) no existe todavía, y fingir lo contrario aquí sería
  la misma alucinación normativa que este producto existe para evitar.

## 5. Casos de uso

1. El arquitecto mide una planta por conversación, la Skill encuentra un
   hallazgo real (p. ej. el solape de `v2s.dxf`, VT1/3), y pide "genérame la
   memoria de esta medición" (o pulsa un botón equivalente). Recibe un
   documento descargable con el hallazgo, su evidencia y su procedencia.
2. La medición no encuentra ningún hallazgo: el documento lo dice
   explícitamente ("sin incidencias en esta comprobación"), no omite la
   sección ni la deja vacía sin explicación.
3. El arquitecto pide la memoria de una pregunta que no llegó a ejecutar
   ninguna Skill (p. ej. "¿cuánto cuesta?", fuera de alcance): no hay acta
   que documentar, y el sistema lo dice en vez de generar un documento vacío
   o inventado.

## 6. Casos límite

- **Acta con `no_comprobado` largo** (limitaciones de la Skill y de cada
  capacidad que usó, derivadas automáticamente): aparecen todas, sin
  truncar — es exactamente la sección que un arquitecto necesita leer entera
  antes de fiarse del resto.
- **Varias viviendas en el mismo plano** (`v2s.dxf`, `V5.dxf`): decisión de
  diseño pendiente en la tarea `MJ-1` (ver §11) — ¿una memoria por vivienda o
  una consolidada con una sección por vivienda? Se decide con datos del
  acta real, no a priori.
- **Fallo de generación del documento** (librería de render rota, acta
  corrupta): error explícito al arquitecto, igual que ya hace
  `/api/informe-pdf` — nunca un documento parcial servido como si estuviera
  completo.
- **El acta cambia entre la conversación y la descarga** (el arquitecto pide
  la memoria más tarde, en otra sesión): el acta ya está sellada
  (`Acta.sello`) en el momento de la ejecución — la memoria se genera del
  acta ya emitida, nunca revalidando ni recalculando nada de nuevo.

## 7. Flujo del usuario

1. El arquitecto obtiene una respuesta real en el panel de conversación
   (tarjeta "Hallazgo" o "Sin incidencias", ver `static/app.js::convTarjetaHallazgo`).
2. Un botón junto a esa tarjeta — "Descargar memoria de superficies" — no
   uno nuevo y separado del flujo, el mismo sitio donde ya vive "Ver el acta
   de procedencia completa".
3. El backend reconstruye o reutiliza el `Acta` ya levantada para esa
   ejecución y la pasa al renderizador de documento.
4. Descarga directa (mismo patrón que `/api/informe-pdf`: `Content-Disposition: attachment`).

## 8. Criterios de aceptación

1. El documento generado contiene, palabra por palabra o cifra por cifra,
   solo lo que ya estaba en `Acta.datos`/`Acta.pasos`/`Acta.no_comprobado` —
   comprobado con un test que compara el documento contra el acta de origen,
   no con una fijación visual.
2. Ninguna cifra del documento carece de procedencia — mismo `test_no_orphan_numbers`
   del §13 de `CLAUDE.md`, aplicado a este documento nuevo.
3. Ningún texto del documento afirma cumplimiento normativo ni cita un
   artículo — test que falla si aparece "CTE", "cumple", "DB-", "normativa"
   fuera de la leyenda de borrador fija.
4. La leyenda de borrador aparece siempre, en la primera página.
5. Un acta sin ningún dato (pregunta fuera de alcance) no genera documento:
   error explícito, no un PDF/DOCX vacío.
6. La sección "Qué no se ha comprobado" aparece siempre, íntegra, aunque
   esté vacía ("nada que declarar" — nunca omitida en silencio).

## 9. Riesgos

**R-1 · El nombre invita a sobreprometer.** "Memoria justificativa" suena a
memoria legal completa. *Mitigación:* título del documento y leyenda
explícitos ("Apartado de superficies — borrador de apoyo, sin valor
normativo"), nunca "Memoria justificativa" a secas en la portada.

**R-2 · Formato del documento: DOCX vs. PDF.** El §M4 de `CLAUDE.md` pide
"docx/xlsx", y una memoria real se edita en Word antes de entregarse — pero
`python-docx` sería una dependencia nueva, y `reportlab` (PDF) ya está en
`requirements.txt` y probado en `analyzer/pdf_report.py`. *Recomendación de
este PRD:* empezar por PDF (cero dependencia nueva, reduce esta tarea a la
mitad), DOCX como tarea de seguimiento explícita si Pablo confirma que hace
falta editar el documento y no solo incorporarlo. No se asume DOCX por
defecto.

**R-3 · Compite por tiempo con `REFACTOR_MASTERPLAN.md`.** Es capacidad
nueva, no endurecimiento — entra en la cola normal de decisión de Pablo, no
salta delante de lo ya priorizado ahí.

**R-4 · Se demuestra y no se usa.** Mismo riesgo de fondo que `OP-11` y el
copiloto (R-4 de su propio PRD). *No se mitiga con tecnología*: si nadie
pide "genérame la memoria" en la prueba real, el producto no invierte más
aquí — mismo criterio que ya aplicó ese PRD.

## 10. Impacto sobre módulos existentes

**Nuevo:** `analyzer/memoria_justificativa.py` (render del documento a
partir de un `Acta`, mismo patrón que `analyzer/pdf_report.py` pero
consumiendo `agente.acta.Acta` en vez de la salida de `evaluator.py`), un
endpoint nuevo (`/api/memoria-justificativa` o similar — a decidir en `MJ-1`),
botón en `static/app.js` junto a `convTarjetaHallazgo`, y sus tests.

**Se consume sin modificar:** `agente/acta.py` (`Acta`, `levantar()`,
`levantar_de_pasos()`), `agente/ejecucion.py`, `analyzer/marca_borrador.py`
(la leyenda), `reportlab` (ya en `requirements.txt`).

**No se toca:** `analyzer/pdf_report.py`/`/api/informe-pdf` (sigue siendo el
informe de calidad arquitectónica de `evaluator.py`, un documento distinto
con una fuente distinta — no se fusionan), `analyzer/acta_legible.py` (sigue
siendo la vista HTML de verificación, este documento es la vista
descargable/entregable, no la sustituye).

## 11. Plan de implementación

| # | Tarea | ~ |
|---|---|---|
| **MJ-1** | Decidir formato (PDF vs. DOCX, ver R-2) y estructura para múltiples viviendas (ver §6) — documento de decisión corto, no código. | 0,5h |
| **MJ-2** | `analyzer/memoria_justificativa.py`: `Acta` → documento, reutilizando `_ESTILO`/patrones de `pdf_report.py` o `acta_legible.py` según MJ-1. Sin normativa, con leyenda de borrador. | 2h |
| **MJ-3** | Endpoint HTTP: recibe una referencia a la ejecución (o el acta ya en la respuesta de `/api/preguntar`) y devuelve el documento como descarga. | 1,5h |
| **MJ-4** | Botón "Descargar memoria de superficies" en `static/app.js`, junto a la tarjeta de hallazgo. | 1h |
| **MJ-5** | Tests de los 6 criterios de aceptación, incluido el guardián de "nunca normativa sin corpus" (criterio 3). | 2h |

## 12. Plan de pruebas

Mismo criterio que el resto de la suite de esta sesión: un test que compara
el documento generado contra el `Acta` de origen campo a campo (no una
fijación visual del PDF/DOCX entero, que se rompe con cualquier cambio de
maquetación), más los guardianes estáticos de texto prohibido (normativa,
cumplimiento) sobre el módulo de render. Reutiliza el `ClienteGuionizado`
para generar un acta real de prueba sin gastar tokens, mismo patrón que
`tests/test_preguntar_endpoint.py`.

## 13. Métricas para medir el éxito

Cuántas veces se pulsa "Descargar memoria" de verdad, en sesiones reales con
Pablo o con un arquitecto de prueba — no una métrica de éxito técnico
(el documento se genera sin fallar), que ya la cubren los tests. Si en la
prueba real nadie lo descarga, es la misma señal que R-4: no se invierte
más aquí sin evidencia de que se usa.

## 14. Posibles motivos para NO implementar la idea

El volumen de uso real de la conversación/medición (`/api/preguntar`) es
todavía bajo — es una capacidad de esta misma sesión, sin datos de uso real
todavía. Construir una capa de documento encima de una capacidad que nadie
ha probado en producción es exactamente el patrón que R-4 (y el propio
`OP-11`) ya señaló como riesgo de fondo de todo ArchMuse. **Alternativa
honesta:** esperar a que la Skill de medición tenga uso real demostrado
(aunque sea de un solo arquitecto de prueba) antes de invertir aquí, y
mientras tanto dejar que el arquitecto siga usando "Ver el acta de
procedencia completa" (ya existe) copiando a mano lo que necesite. Si Pablo
decide seguir de todas formas, la razón legítima es que "generar el
informe" es la mitad explícita del value prop de V1 (§1 de `CLAUDE.md`) y
no depende de que el resto tenga tracción todavía — pero es una apuesta, no
una certeza, y este documento no la disfraza de otra cosa.

---

**Decisión:** Aprobado y construido (2026-08-19). Verificado en vivo contra
`v2s.dxf` real. Ver `PROGRESS.md`, noche 11.
