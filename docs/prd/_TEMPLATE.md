# PRD — [Nombre corto de la capacidad]

**Estado:** Borrador · **Fecha:** AAAA-MM-DD · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 1. Problema que resuelve

¿Qué dolor real, hoy sin resolver, motiva esto? Citar de dónde viene (petición directa de Pablo, hallazgo de `TECH_REVIEW.md`/`MOAT_ANALYSIS.md`, hito de `NORTH_STAR_2031.md`, etc.), no inventar un problema para justificar una solución ya decidida.

## 2. Usuario afectado

Quién lo usa de verdad: ¿arquitecto individual, estudio con equipo, promotor, colegio profesional, aseguradora? ¿Es el usuario de hoy o el usuario objetivo de un horizonte futuro de `NORTH_STAR_2031.md`?

## 3. Objetivo de negocio

Por qué le importa a ArchMuse como negocio, no solo como producto. Conectar con la estrategia de `MOAT_ANALYSIS.md` (retención, foso, monetización) cuando aplique.

## 4. Objetivo técnico

Qué debe ser cierto del sistema una vez implementado, en términos de comportamiento observable — no de implementación.

## 5. Casos de uso

Los escenarios principales, con el flujo esperado en cada uno.

## 6. Casos límite

Qué pasa en los bordes: datos ausentes, entradas inválidas, escenarios que hoy ya rompen algo (revisar `TECH_REVIEW.md` antes de asumir que un caso límite es nuevo — puede que ya sea un bug conocido).

## 7. Flujo del usuario

Paso a paso, desde que el usuario inicia la acción hasta que obtiene el resultado.

## 8. Criterios de aceptación

Lista verificable de "esto está hecho cuando...". Deben poder comprobarse sin ambigüedad.

## 9. Riesgos

Técnicos, de producto, y de negocio. Incluir explícitamente si esto compite por tiempo de desarrollo con tareas ya priorizadas en `REFACTOR_MASTERPLAN.md`.

## 10. Impacto sobre módulos existentes

Qué archivos/módulos de `analyzer/`, `app.py` o `static/index.html` toca, y qué otros módulos consumen esos mismos datos y podrían verse afectados indirectamente.

## 11. Plan de implementación dividido en pequeñas tareas

Mismo formato que `REFACTOR_MASTERPLAN.md`: tareas independientes, de máximo 2 horas cada una.

## 12. Plan de pruebas

Cómo se verifica que funciona y que no rompe nada existente — idealmente contra la misma suite de test golden-master prevista en `REFACTOR_MASTERPLAN.md` (tarea 18), si ya existe para entonces.

## 13. Métricas para medir el éxito

Cómo se sabrá, con datos y no con impresión, si esto funcionó una vez en producción.

## 14. Posibles motivos para NO implementar la idea

Argumento honesto en contra, aunque el resto del documento sea a favor. Si la conclusión es "no merece la pena todavía" o "hay una alternativa mejor", decirlo aquí explícitamente y proponerla — no forzar una recomendación positiva por inercia.

---

**Decisión:** _pendiente de revisión por Pablo_
