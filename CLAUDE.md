# ArchMuse — Instrucciones de proceso

## Regla de proceso obligatoria: PRD antes de código

**A partir de 2026-07-31, ninguna capacidad nueva del producto se implementa directamente.**

Cuando Pablo pida una mejora o funcionalidad nueva, el primer entregable es un **PRD** en `docs/prd/`, no código. No se escribe ni se modifica código de producto hasta que Pablo apruebe explícitamente el PRD.

Usar `docs/prd/_TEMPLATE.md` como base. Nombrar cada PRD como `docs/prd/AAAA-MM-DD-nombre-corto.md`.

El PRD debe incluir, como mínimo, estas 14 secciones:

1. Problema que resuelve
2. Usuario afectado
3. Objetivo de negocio
4. Objetivo técnico
5. Casos de uso
6. Casos límite
7. Flujo del usuario
8. Criterios de aceptación
9. Riesgos
10. Impacto sobre módulos existentes
11. Plan de implementación dividido en pequeñas tareas
12. Plan de pruebas
13. Métricas para medir el éxito
14. Posibles motivos para NO implementar la idea

### Postura al escribir un PRD: CTO, no ejecutor de tickets

Si una idea aporta poco valor, es prematura, o contradice la visión ya establecida del producto, decirlo explícitamente en el PRD (sección 14) y proponer una alternativa mejor — no implementar por implementar. Evaluar cada propuesta contra la visión y la estrategia ya documentadas en la raíz del proyecto:

- `PROJECT_AUDIT.md` — qué es ArchMuse, arquitectura, estado real de cada módulo.
- `TECH_REVIEW.md` — calidad técnica, deuda técnica, bugs conocidos. **Nota (2026-08-16):** el bug crítico de tipología/zona climática en `/api/analizar` que este documento describe como "sin corregir" ya está corregido — verificado leyendo `app.py`. Este documento tiene fecha de julio y el repositorio ha tenido 54 commits desde entonces (ver `ROADMAP_VISION_ARQUITECTONICA.md` §1); tratar sus hallazgos como orientativos, no como estado actual, hasta que se refresque.
- `ROADMAP_VISION_ARQUITECTONICA.md` — brújula oficial (aprobada por Pablo, 2026-08-16) para todo lo relacionado con el visor 3D/entorno, asesor legal/urbanístico, sostenibilidad y navegación. Cualquier PRD nuevo en estas áreas debe evaluarse contra su §3 (análisis honesto por pilar) y su §6 (secuencia recomendada), no solo contra `NORTH_STAR_2031.md`.
- `REFACTOR_MASTERPLAN.md` — plan de endurecimiento ya priorizado; cualquier PRD nuevo debe tener en cuenta si compite por el mismo tiempo de desarrollo que esas tareas, no asumir que empieza en un proyecto ya saneado.
- `MOAT_ANALYSIS.md` — qué es defendible y qué no; qué funcionalidades actuales aportan complejidad sin foso real (ver especialmente el visor 3D y el percentil comparativo).
- `DESTROY_ARCHMUSE.md` — los ataques más plausibles contra el producto tal como está; cualquier PRD que ignore estas debilidades conocidas debe justificar por qué.
- `NORTH_STAR_2031.md` — la visión a la que debe acercar cada capacidad nueva, y los hitos de 1/3/6/12/24 meses ya definidos hacia ella.

**Esta regla de proceso (PRD antes de implementar) aplica a capacidades nuevas del producto.** Las correcciones de bugs y las tareas de endurecimiento ya planificadas en `REFACTOR_MASTERPLAN.md` no son "capacidad nueva" — son arreglos sobre lo que ya existe — así que no requieren un PRD nuevo por defecto; si surge duda sobre si algo cuenta como "nuevo" o como "corrección", preguntar antes de asumir.
