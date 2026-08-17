# E2 — Registro de la implementación real de la persistencia del modelo

**Fecha:** 2026-08-11 · **Tipo:** registro de implementación · **Estado:** ejecutado, sin commit
**Plan:** [`docs/prd/2026-08-11-e2-persistencia-modelo.md`](../prd/2026-08-11-e2-persistencia-modelo.md)
**Hereda de:** [`2026-08-11-e1-implementacion.md`](2026-08-11-e1-implementacion.md)

Mismo criterio que el registro de E1: esto no repite el PRD, registra qué se construyó de verdad y en qué se
desvió, con los números medidos.

---

## 1. Qué cambió

```
analyzer/storage.py     +columna `modelo` (migración idempotente), guardar_proyecto(grafo=None),
                         obtener_modelo() — verifica el sellado (I8) antes de devolver
app.py                  construye el modelo del proyecto una vez, tras leer_plano(); se lo pasa
                         a guardar_proyecto(); best-effort (no bloquea el análisis si falla)
modelo/compat.py        grafo_de_adyacencia() memoizado por identidad de objeto (weakref, no id()
                         ingenuo) — la misma vivienda no se reconstruye dos veces
```

`analyzer/circulation.py`: **sin cambios en esta etapa** — la memoización vive en `compat.py`, no en el
consumidor. El diff de `circulation.py` que aparece en `git diff` es el de E1, no de E2.

Nuevos: `tests/test_e2_persistencia.py` (35 comprobaciones), `tests/test_e2_construccion_unica.py` (10
comprobaciones), este documento.

## 2. Neutralidad — medida

| Comprobación | Resultado |
|---|---|
| Payload de `/api/analizar` guardado con modelo vs. sin modelo | **byte a byte idéntico** (salvo `proyecto_id`, que ya variaba antes de E2) |
| G1–G9 | 9/9 sin cambios |
| K1–K4 (canario) | 11/11, mismo patrón que al cierre de E1 |
| Suite completa | 58 ficheros (56 de E1 + 2 nuevos de E2), 57 OK, 1 FALLO — el conocido |
| CAP-1…CAP-5 | mismos recuentos que al cierre de E1 (88, 120, 68, 47, 177, 34, 63, 39) |
| Circulación | `test_ocupacion.py`, `test_modelo_compat.py`, `test_golden_circulacion.py` sin cambios |

## 3. Desviación

### D-E2.1 — La métrica "12 construcciones → 1" del PRD no es la que se implementó; la real es "12 → 6 + 1"

- **Decisión original (PRD §0 y §14):** el borrador medía 12 construcciones del modelo por análisis sobre
  `ejemplo.dxf` y fijaba como métrica de éxito "12 → 1".
- **Problema encontrado, al escribir el test que la comprueba.** "1" describe una arquitectura que el propio PRD
  no eligió: para llegar a una única construcción por análisis, el grafo de proyecto construido una vez en
  `app.py` (E2.4) tendría que *ser* el que usa `circulation.py`, en vez de que `circulation.py` siga pidiendo
  submodelos por vivienda a través de `compat.grafo_de_adyacencia`. Eso es exactamente lo que C-E2.3 decidió NO
  hacer, y por una razón que el propio PRD ya daba: exigiría un parámetro nuevo en `evaluate_circulation()`,
  `api_serializer.py` y `chain_effects.py` — tres ficheros más tocados por el mismo resultado medible, en contra
  de "el cambio mínimo, nada de refactorización general".
- **Solución aplicada:** se implementó C-E2.3 tal como está escrito (memoización por identidad de objeto en
  `compat.py`), y se corrige la métrica para que describa lo que el código realmente hace, medido por
  `tests/test_e2_construccion_unica.py`:
  - Las **12** llamadas a `evaluate_circulation()` (2 por vivienda × 6 viviendas) pasan a producir **6**
    construcciones reales — una por vivienda, no dos. Es la mitad, no un doceavo.
  - Aparte, y por primera vez, `app.py` construye **1** modelo de **proyecto completo**, una vez por análisis,
    para poder persistirlo (E2.4) — una construcción nueva, de un tipo distinto (proyecto entero, no vivienda
    suelta), que **no sustituye** a las 6 anteriores porque no están conectadas entre sí.
  - Total medido: **12 → 6 + 1**, no **12 → 1**.
- **Impacto:** ninguno sobre el resultado — sólo sobre cómo se describe el ahorro. El ahorro real (la mitad de
  las construcciones por vivienda, cero coste añadido en el caso común) sigue siendo una mejora medible y
  verificada, simplemente no es la que el borrador anunciaba antes de medirla.
- **Por qué sigue siendo compatible con la arquitectura:** unificar los submodelos por vivienda con el modelo de
  proyecto es exactamente el tipo de unificación que E1 ya dejó pendiente y documentada (`docs/design/2026-08-11-e1-implementacion.md`
  §5, "El grafo se construye por vivienda... conviene no repetirlo por regla cuando migren más consumidores"). No
  se resuelve en E2 por la misma razón que no se resolvió en E1: no hay todavía un segundo consumidor que lo
  necesite de verdad, y forzarlo ahora sería la refactorización general que el encargo prohíbe explícitamente.
  Queda igual de pendiente que antes, con el número correcto esta vez.

**Lo que NO se desvió:** C-E2.1 (columna, no tabla), C-E2.2 (sin semilla, `concept_id` no derivado de
`proyecto_id`), C-E2.4 (payload público sin cambios) — las tres se implementaron tal como las cerró el PRD, y las
tres están comprobadas por test, no supuestas.

## 4. Lo que E2 deja pendiente, dicho por su nombre

- **Un solo modelo por análisis, de verdad.** Hoy conviven el modelo de proyecto (nuevo, sólo para persistir) y
  los submodelos por vivienda (de E1, memoizados pero no unificados). Unificarlos es la etapa natural cuando
  `circulation.py` dejen de ser su único consumidor con lógica propia de construcción.
- **Emparejamiento entre versiones** (`identidad.emparejar()`): sigue lanzando `NotImplementedError`. Persistir
  una versión no es lo mismo que poder compararla con la siguiente.
- **`/api/generar` sin modelo:** los proyectos generados por IA siguen sin `modelo/` (fuera de alcance,
  explícito).
- **Endpoint HTTP del modelo:** `obtener_modelo()` existe y funciona; no hay ruta que lo publique. Es decisión de
  producto de una etapa que tenga quien lo consuma.
- **Tabla de versiones (`version_modelo`):** sigue necesitando el emparejamiento primero, como ya decía C-E2.1.

---

**Estado:** implementado y verificado, sin commit. `git diff` sobre producción: tres ficheros —
`analyzer/storage.py`, `app.py` (nuevos en esta etapa) y `analyzer/circulation.py` (diff heredado de E1, sin
cambios nuevos en E2).
