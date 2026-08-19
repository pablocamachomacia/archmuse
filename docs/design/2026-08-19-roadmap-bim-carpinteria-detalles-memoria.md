# Roadmap hacia BIM + carpintería + detalles constructivos + memoria justificativa

> Documento de decisión. Pedido explícito de Pablo, 2026-08-19 (noche 7).
> No es código, no es un PRD de una tarea — es el orden vinculante de cuatro
> capacidades que Pablo quiere ver en ArchMuse, y la razón de que ese orden
> no sea negociable capacidad a capacidad.

## 0. El pedido, tal cual

Pablo quiere que ArchMuse llegue a hacer, con el tiempo:

1. Detalles constructivos.
2. Planos de carpintería.
3. Todo ello desde un modelo BIM real, no desde un DXF 2D.
4. Memoria justificativa.

**Ninguno de los cuatro es alcanzable "rápido"**, y no son cuatro tareas en
paralelo: son una cadena. El motivo no es de esfuerzo, es de dato — cada
capacidad de la lista necesita algo que la anterior deja construido, y
saltarse un eslabón no ahorra tiempo, produce el defecto exacto que el §1 de
`CLAUDE.md` (la regla de oro) prohíbe: un número, un plano o un detalle en
pantalla sin una tool determinista y verificada detrás.

## 1. Por qué este orden y no otro

| # | Paso | Por qué va aquí y no antes |
|---|------|------------------------------|
| 1 | **Cerrar V1** (medición + acta + conversación) | En marcha esta misma sesión. Es el cimiento: `Provenance`, `AreaFigure` tipada, reconciliación — sin esto, ningún dato nuevo tendría dónde colgar su procedencia. |
| 2 | **Memoria justificativa automática**, a partir de lo ya medido | Única pieza del pedido alcanzable **dentro de V1**: el acta de procedencia legible (`analyzer/acta_legible.py`) y la reconciliación de cifras ya existen — ver `docs/AGENTE_BACKLOG.md` §13.7. Redactar la memoria es reordenar y prosear datos que ArchMuse ya midió, no inventar una capacidad nueva. |
| 3 | **Lectura de modelo BIM real** (Revit/IFC con parámetros ricos, no solo DXF 2D) | Arranque de V2. `NORTH_STAR_2031.md` ya sitúa esto como el hito de 12-24 meses, y explícitamente como **PoC de viabilidad antes de comprometer el resto de la inversión** (§ hito de validación, línea ~180) — no se construye a ciegas. |
| 4 | **Corpus normativo citable** (CTE estructurado, cita literal + artículo) | Requisito **antes** de justificar nada técnico — no antes de leer BIM, pero sí antes de generar cualquier detalle o carpintería con pretensión normativa. El corpus hoy está vacío (ver `[[archmuse-adr-cerebro-arquitecto]]`); `analyzer/referencias_normativas.py` ya documenta por qué sus referencias actuales **no son una cita legal certificada** — ese hueco es exactamente lo que este paso cierra. |
| 5 | **Motor de detalles constructivos**: biblioteca de soluciones tipo, verificada por un humano | Nunca generado libremente por el modelo — una biblioteca de soluciones ya validadas por un arquitecto colegiado, seleccionada por regla determinista, no redactada por el LLM caso a caso. |
| 6 | **Planos de carpintería**: generados desde BIM (paso 3) + reglas del paso 5 | `docs/AGENTE_BACKLOG.md` §"evaluación comercial" ya midió esto contra un plano real (`v2s.dxf`): las puertas traen dimensión en el nombre del bloque, **las ventanas no** — son geometría sin datos asociados. Sin BIM real (paso 3), la carpintería sale del mismo problema que ya se detectó y se rechazó una vez (`OP-13`, pospuesta explícitamente por esto). Revisión humana obligatoria antes de exportar. |
| 7 | **Integración completa y trazable** de BIM + normativa + detalles + carpintería + memoria | V3. Cada pieza anterior con su procedencia propia; este paso las une sin que ninguna deje de llevar la suya. |

## 2. La regla dura

> **No se construye ningún paso saltándose el anterior — ni con urgencia del
> usuario en el momento.** Un plano de carpintería o un detalle constructivo
> generado sin modelo BIM real y sin corpus normativo verificado detrás es
> indistinguible de una alucinación con buena presentación: exactamente el
> dato peligroso que prohíbe la regla de oro del §1.

**Cómo se aplica en la práctica, para mí (el agente) en sesiones futuras:**
si Pablo pide directamente uno de los pasos 5, 6 o 7 antes de que el paso
del que depende esté cerrado, **no lo ejecuto directo**: señalo
explícitamente qué paso previo falta y pido confirmación antes de tocar
código. Esto no es desconfianza hacia el pedido — es la misma regla que ya
gobierna el resto del repositorio (`test_no_orphan_numbers`, la prohibición
de afirmar cumplimiento normativo global) aplicada a un roadmap, no solo a
una tool.

## 3. Qué NO decide este documento

- No fija fechas ni duración por paso — es orden, no calendario.
- No sustituye el proceso de PRD de `CLAUDE.md`: cada paso, al llegar su
  turno, sigue necesitando su propio PRD en `docs/prd/` antes de escribir
  código de producto.
- No reabre `D-12` ni ninguna decisión ya tomada y documentada en
  `PROGRESS.md` — es ortogonal.

## Referencias

- `NORTH_STAR_2031.md` — horizonte 12/24 meses ya sitúa BIM y memoria
  justificativa en esta misma secuencia general.
- `docs/AGENTE_BACKLOG.md` §13.7 y la sección "evaluación comercial" —
  medición real sobre `v2s.dxf` que motiva los pasos 2 y 6.
- `analyzer/referencias_normativas.py` — el hueco exacto que cierra el paso 4.
- Memoria del agente: `[[archmuse-adr-cerebro-arquitecto]]`,
  `[[archmuse-plan-migracion]]`, `[[archmuse-reglas-de-ejecucion]]`.
