# PRD — Informe de defensa por proyecto (primer producto cobrable)

**Estado:** Borrador · **Fecha:** 2026-08-22 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> **Qué es esto y qué no es.** Este PRD define el primer entregable de pago de
> ArchMuse: un informe por proyecto (100–300 €) que un arquitecto de Madrid
> puede adjuntar a su expediente como evidencia de control sistemático previo a
> su firma. **No es un motor nuevo ni una skill nueva**: es el empaquetado
> comercial de piezas que ya existen o están en ejecución esta semana —
> el corpus firmado DB-SI 3 (PRD `2026-08-22-corpus-firmado-dbsi3-evacuacion.md`,
> aprobado), el patrón acta→documento descargable
> (PRD `2026-08-19-memoria-justificativa-automatica.md`, implementado) y la
> skill `revision.recorridos_de_evacuacion`.
>
> Justificación de mercado: análisis de competencia del 2026-08-22 (sesión de
> planificación con Pablo). Resumen: existen ya dos competidores españoles
> directos — Tektia (pre-verificación IA, 96% reglas deterministas, Barcelona
> cubierta, **Madrid "en desarrollo"**) y D-LINIEX (checker autoservicio,
> 49–99 €/mes) — y ninguno tiene corpus con acta firmada por colegiado. El
> anclaje de precio por proyecto lo pone el propio mercado: Tektia se compara
> contra "el técnico que cobra 200–500 €/proyecto" y las ECU de Madrid cobran
> tarifas regladas por verificación de expediente.

---

## 1. Problema que resuelve

Dos problemas, uno del cliente y uno del negocio:

- **Del arquitecto:** firma proyectos sin un control sistemático documentado.
  El coste que teme no es el tiempo de revisar — es el requerimiento de visado
  y la responsabilidad civil posterior (`MOAT_ANALYSIS.md` §1). Hoy ArchMuse
  ya sabe comprobar recorridos de evacuación con cita firmada (desde el
  martes 26, si el PRD del corpus se ejecuta según plan), pero el resultado
  vive en una conversación (`/mvp`, `/api/preguntar`) y en un acta-pantalla:
  **no hay nada que el arquitecto pueda adjuntar a un expediente ni enseñar a
  un cliente o a su aseguradora.**
- **Del negocio:** ArchMuse no tiene ningún producto cobrable. El análisis de
  mercado del 2026-08-22 concluye que la categoría "checker por suscripción"
  ya está anclada a la baja (D-LINIEX 49–99 €/mes) y que el hueco defendible
  es el informe caro por responsabilidad transferida, no la utilidad barata
  por tiempo ahorrado. La ventana madrileña caduca cuando Tektia complete su
  cobertura de Madrid.

Origen: decisión de Pablo (2026-08-22, sesión de planificación, opción
"PRD informe de defensa" elegida explícitamente).

## 2. Usuario afectado

- **Comprador y usuario:** arquitecto colegiado en Madrid, proyecto
  residencial (obra nueva o rehabilitación), en el momento de cerrar el
  proyecto antes de visado. Es el comprador natural de hoy según la secuencia
  de `MOAT_ANALYSIS.md` (§ secuencia, paso 1).
- **Lector del informe (no usuario):** el visador del colegio, el cliente del
  arquitecto, o su aseguradora — el informe se redacta para poder ser leído
  por ellos sin explicación adicional.
- **Comprador futuro (fuera de alcance aquí, en el radar):** ECU/consultoría
  de licencias de Madrid, que revisa expedientes por volumen. Este PRD debe
  no cerrarle la puerta (el informe debe poder emitirse "por encargo de"
  un tercero), pero no construye nada específico para él.

## 3. Objetivo de negocio

Primer euro en 3–4 meses. Precio objetivo: **100–300 € por informe**,
anclado contra el técnico humano (200–500 €) y contra las tarifas regladas de
las ECU — nunca contra D-LINIEX (49–99 €/mes), que es otra categoría.

Por qué este producto y no otro (test de precio del consejo, 2026-08-22): una
función que ahorra horas compite contra el tiempo de un becario; una función
que permite documentar que el proyecto pasó un control sistemático antes de la
firma compite contra una póliza y contra el coste de un requerimiento. El
informe de defensa es lo segundo. El diferencial visible que ningún competidor
tiene: **el acta de curación firmada por arquitecto colegiado** detrás de cada
regla aplicada, mostrada en el propio informe como sello verificable.

Además: cada informe vendido genera un proyecto real analizado — el activo de
datos del Pilar 3 de `MOAT_ANALYSIS.md` empieza a acumularse con clientes, no
con ejemplos.

## 4. Objetivo técnico

Comportamiento observable una vez implementado:

1. Dado un proyecto ya analizado en ArchMuse (medición de planta hecha, skill
   de evacuación ejecutada), existe una acción "Generar informe de defensa"
   que produce un **documento descargable** (PDF; DOCX si el coste es
   marginal reutilizando el generador de la memoria justificativa) con:
   - Portada identificando proyecto, fecha, versión de ArchMuse y **código de
     verificación** del informe.
   - Una sección por comprobación realizada: qué se comprobó, valor medido,
     umbral aplicado, **cita literal del artículo con referencia BOE**, y
     resultado (cumple / no cumple / no evaluable) — todo procedente del acta
     de la skill, cero cálculo nuevo en la capa de informe.
   - El **sello de curación**: por cada regla aplicada, quién la validó
     (nombre, colegiatura, fecha del acta de curación), con la huella
     (`hash`) de la regla firmada — datos que ya existen en el bloque
     `firma` del corpus (PRD corpus firmado, §4.4).
   - La sección **"Qué NO se ha comprobado"**, siempre presente y no
     opcional — mismo invariante que la memoria justificativa implementada y
     que `CLAUDE.md` §7 (nunca afirmar cumplimiento global).
2. El informe solo incorpora comprobaciones respaldadas por reglas
   `estado: FIRMADA`. Una regla en borrador o `VERIFICADA_AUTOMATICA` no
   puede aparecer como comprobación afirmada — a lo sumo en la lista de "no
   comprobado" como cobertura futura. Fail-closed, igual que el loader.
3. Ninguna cifra del informe carece de procedencia (`test_no_orphan_numbers`
   aplica al documento igual que al resto del sistema).

## 5. Casos de uso

1. **Venta directa:** un arquitecto con proyecto de vivienda en Madrid sube su
   DXF / completa la medición conversacional, ejecuta la revisión de
   evacuación, y compra/descarga el informe de defensa para adjuntarlo al
   expediente de visado.
2. **Hallazgo negativo (el caso más valioso):** el informe muestra un
   recorrido de 27,4 m contra el umbral de 25 m con la cita de la tabla 3.1 —
   el arquitecto corrige antes de visar. El informe re-generado tras la
   corrección muestra el nuevo valor. Dos informes = dos actas, sin
   sobrescritura.
3. **Demostración comercial:** Pablo (o un arquitecto colegiado ante sus colegas) enseña
   un informe de ejemplo con el sello de curación visible como argumento de
   venta — "cada regla de este informe la validó un colegiado contra el PDF
   oficial; este es el acta".
4. **Verificación por un tercero:** un visador o aseguradora que reciba el
   informe puede cotejar el código de verificación y la huella de las reglas
   contra el acta de curación publicada (mismo mecanismo de auditoría que el
   PRD del corpus, caso de uso 4).

## 6. Casos límite

- **Proyecto sin medición completa:** si la skill no pudo medir (planta sin
  circulación identificable, DXF sin convención de capas), el informe no se
  genera "a medias en silencio": o se genera declarando explícitamente la
  comprobación como `no evaluable` con el motivo, o se bloquea con mensaje
  claro. Nunca un informe con huecos silenciosos.
- **Corpus parcialmente firmado:** entre el martes 26 y la firma del núcleo
  DB-SUA, el informe cubrirá solo evacuación. El alcance del informe se
  declara en la portada ("este informe cubre: recorridos de evacuación
  DB-SI 3; no cubre: …") — vender un informe estrecho y honesto es aceptable;
  aparentar amplitud no.
- **Regla firmada superseded o alterada después de emitir un informe:** el
  informe emitido es un documento congelado con su fecha y las huellas de las
  reglas que usó; si el corpus cambia después, los informes antiguos no se
  invalidan retroactivamente, pero uno nuevo usará el corpus vigente.
- **El cliente pide "certificado de cumplimiento":** el informe nunca usa esa
  palabra. Título y redacción fijados en este PRD: "Informe de revisión
  sistemática" / "comprobaciones realizadas". Es la línea roja de
  `CLAUDE.md` §7 y, a la vez, el argumento diferencial (transparencia como
  marca, Pilar 2 de `MOAT_ANALYSIS.md`).
- **Cobro:** V1 del cobro es manual (transferencia/Bizum y Pablo habilita la
  descarga) — no se construye pasarela de pago hasta que haya >5 clientes.
  Evitar la trampa de construir Stripe antes que clientes.

## 7. Flujo del usuario

1. El arquitecto entra en ArchMuse (desplegado en web con acceso por
   invitación — ver §11, dependencia D2), crea proyecto y sube su DXF o
   completa la entrevista de medición.
2. Ejecuta la revisión (hoy: `revision.recorridos_de_evacuacion` vía
   conversación; el botón/atajo directo es parte de este PRD).
3. Ve en pantalla el acta (ya existe) y pulsa "Generar informe de defensa".
4. Descarga el PDF, lo revisa, y lo adjunta a su expediente o lo reenvía.
5. Pablo recibe notificación del informe emitido (para facturar en V1 manual
   y para la métrica de §13).

## 8. Criterios de aceptación

1. Con el corpus firmado del martes 26 cargado, un proyecto de prueba real
   genera un PDF que contiene: portada con código de verificación, cada
   comprobación con cita literal + referencia BOE, el sello de curación con
   nombre/colegiatura/fecha/huella por regla, y la sección "Qué NO se ha
   comprobado".
2. Con una regla degradada a borrador (simulando manipulación), la
   comprobación desaparece de la parte afirmada del informe y el informe lo
   declara — test automatizado.
3. `test_no_orphan_numbers` (o su equivalente aplicado al informe) pasa sobre
   el documento generado.
4. El informe no contiene las palabras "certifica", "cumplimiento del CTE"
   (global) ni "garantiza" — test de redacción sobre la plantilla.
5. Un arquitecto real (el primer lector) lee el informe de
   ejemplo y responde afirmativamente a: "¿adjuntarías esto a un expediente?"
   — criterio de la skill `arquitecto-veterano`, registrado por escrito.
6. Existe una página/una cara de PDF comercial que explica qué es el informe,
   qué cubre, qué no, y su precio — el material con el que se venden los
   primeros 5 pilotos.

## 9. Riesgos

- **Riesgo calendario (el mayor):** este PRD depende del corpus firmado
  (martes 26). Si la sesión del lunes 25 firma menos reglas de las previstas,
  el informe nace más estrecho — aceptable (caso límite 2); lo que no es
  aceptable es retrasar el PRD del corpus por trabajar en este. **Este PRD no
  toca nada hasta que el del corpus cierre su fase de firma.**
- **Compite por tiempo** con `REFACTOR_MASTERPLAN.md` y con el backlog del
  agente: sí. Justificación: es el único camino al primer euro, y el análisis
  de mercado fija urgencia externa (Tektia-Madrid). Las tareas de
  endurecimiento que son prerequisito directo (despliegue, autenticación
  básica, persistencia) se hacen como parte de la dependencia D2, no "algún
  día".
- **Riesgo de confianza:** un informe con un dato incorrecto ante un
  profesional de pago es irrecuperable (`DESTROY_ARCHMUSE.md` §5.1). Por eso
  la capa de informe no calcula nada: reproduce actas. El riesgo residual
  vive en el motor y en el corpus, que ya tienen su propia disciplina.
- **Riesgo de precio:** puede que 100–300 € resulte alto para un informe que
  cubre solo evacuación. Mitigación: precio de lanzamiento en el rango bajo
  (100–150 €) mientras la cobertura sea estrecha, subida al ampliar DB-SUA;
  el piloto (5 arquitectos vía el colegio profesional) existe precisamente para
  descubrir el precio real antes de generalizarlo.
- **Riesgo legal:** el informe podría interpretarse como asunción de
  responsabilidad de ArchMuse. Mitigación: la redacción de alcance/limitación
  ya descrita + revisión del texto legal del pie del informe antes del primer
  cliente de pago (consulta puntual, no proyecto).

## 10. Impacto sobre módulos existentes

- **Reutiliza sin modificar:** `agente/acta.py` (fuente de datos),
  el corpus firmado y su bloque `firma` (`normativa/`), la skill
  `revision.recorridos_de_evacuacion`, y el generador documento-desde-acta de
  la memoria justificativa (PRD 2026-08-19, implementado) como base del
  render.
- **Nuevo:** plantilla/generador del informe de defensa (módulo propio, junto
  al de la memoria justificativa), acción en la UI (`/mvp`), registro de
  informes emitidos (código de verificación → acta usada, persistido).
- **Consumidores indirectos a vigilar:** `analyzer/pdf_report.py` (el PDF
  antiguo de hallazgos de `evaluator.py`) — NO se toca ni se mezcla: ese
  informe viene de umbrales sin corpus citado y debe seguir claramente
  separado del informe de defensa, para no contaminar el producto cobrable
  con cifras sin procedencia firmada (misma distinción que ya hizo el PRD de
  la memoria justificativa en su §1).
- **Adyacente, sin solape:** `2026-08-17-checklist-cumplimiento-cte.md`
  (Borrador) es un panel interactivo de estado; este PRD es un documento
  congelado y firmado por sesión. Si aquel se implementa algún día, podrá
  alimentar la misma plantilla, no al revés.

## 11. Plan de implementación dividido en pequeñas tareas

**Dependencias previas (no son tareas de este PRD):**
- **D1 — Corpus firmado en producción** (PRD 2026-08-22, aprobado, cierra ~martes 26).
- **D2 — Mínimos para tener un cliente:** despliegue web accesible por URL +
  autenticación básica por invitación + persistencia de proyectos/actas.
  Son endurecimiento (Fase 2 ya prevista en `TECH_REVIEW.md`), no capacidad
  nueva; se planifican como sesión propia. La experiencia de despliegue en
  Railway de ArchSuite es reutilizable.

**Tareas (máx. 2h cada una):**

1. Definir la plantilla del informe (estructura, textos fijos, redacción de
   alcance y limitaciones) como documento estático de ejemplo — sin código.
   Revisión con el criterio `arquitecto-veterano` + lectura del primer lector.
2. Test de redacción: la plantilla no contiene términos prohibidos
   ("certifica", "garantiza", cumplimiento global).
3. Generador: acta de la skill de evacuación → estructura de datos del
   informe (sin render), con test de que toda cifra lleva procedencia.
4. Enriquecimiento con el sello de curación: por regla usada, leer
   `firma.validado_por` + huella del YAML firmado; test con regla degradada
   (criterio de aceptación 2).
5. Render a PDF reutilizando la vía de la memoria justificativa; test golden
   sobre un proyecto fixture.
6. Código de verificación + registro persistente de informes emitidos.
7. Acción en la UI (`/mvp`): botón "Generar informe de defensa" visible tras
   una revisión con acta; estado deshabilitado con motivo si no hay acta
   completa.
8. Informe de ejemplo comercial (proyecto ficticio del corpus de tests) +
   una cara de material de venta con precio.
9. Sesión de precio y lista de pilotos con Pablo: 5 arquitectos objetivo vía
   el colegio profesional, precio de lanzamiento, guion de oferta.

## 12. Plan de pruebas

- Tests unitarios de las tareas 2, 3, 4 y 5 (redacción, procedencia,
  degradación de regla, golden del PDF).
- Test end-to-end: proyecto fixture → medición → skill → informe, verificando
  criterio de aceptación 1 completo.
- La suite existente (~950 tests) permanece en verde: este PRD no toca motor
  ni corpus, cualquier rojo ahí es una regresión introducida por error.
- Prueba de lector real (criterio 5): no automatizable, se registra por
  escrito en el cierre del PRD.

## 13. Métricas para medir el éxito

- **La única que importa:** informes cobrados. Objetivo: primer informe de
  pago ≤ 8 semanas tras cerrar D1+D2; 5 informes cobrados en 16 semanas.
- Secundarias: informes generados (gratis o pago), tasa
  generado→adjuntado-a-expediente (preguntar al piloto), precio aceptado sin
  negociar, y nº de proyectos reales acumulados en el registro (activo de
  datos, Pilar 3).
- Señal de alarma: pilotos que generan el informe pero no lo adjuntan a nada
  — significaría que es una curiosidad, no una defensa, y obligaría a revisar
  el §14 antes de insistir.

## 14. Posibles motivos para NO implementar la idea

Postura honesta en contra, con la respuesta de este PRD a cada una:

1. **"La cobertura es ridícula: un informe de pago que solo mira evacuación."**
   Cierto hoy. Respuesta: el precio de lanzamiento se fija acorde (rango
   bajo), el alcance se declara en portada, y el mismo empaquetado absorbe
   DB-SUA en cuanto su corpus se firme (pipeline ya construido, PRD
   2026-08-21). La alternativa — esperar a "cobertura suficiente" — es
   exactamente la trampa de amplitud contra la que compite D-LINIEX y que el
   consejo vetó. Si aun así el piloto dice "con esto no me vale ni barato",
   la métrica de alarma de §13 lo detectará con 5 clientes, no con 50.
2. **"Tektia puede llegar a Madrid antes y con más parámetros."**
   Puede. Pero no tiene (ni puede improvisar) el acta de curación firmada por
   colegiado — el único eje donde ArchMuse ya es mejor hoy. No implementar
   este PRD no protege de Tektia; deja el eje diferencial sin monetizar.
3. **"Es prematuro: sin multi-tenant real, cobrar es arriesgado."**
   Por eso D2 se limita a invitación + autenticación básica y el cobro V1 es
   manual. Cinco pilotos elegidos a mano no exigen plataforma; exigirla ahora
   sería construir para clientes que aún no existen.
4. **"Compite por tiempo con el cerebro agéntico (espec M0–M4)."**
   Parcialmente falso: M2/M3 (coherencia, normativa citable) son
   precisamente lo que este informe empaqueta; el PRD añade capa de
   presentación y venta, no un desvío de arquitectura. Lo que sí desplaza:
   cualquier trabajo en 3D/generación/hiperrealismo — que ya está vetado
   hasta el primer euro por decisión previa de Pablo (ROADMAP §6).
5. **Alternativa considerada y descartada como primer producto:** vender
   directamente a una ECU/consultoría (ticket mayor). Descartada como
   *primera* jugada por ciclo de venta más largo y por exigir robustez de
   volumen; se mantiene como jugada 2 (la conversación exploratoria con ECUs
   empieza en paralelo, sin construir nada específico todavía).

---

**Decisión:** _pendiente de revisión por Pablo_
