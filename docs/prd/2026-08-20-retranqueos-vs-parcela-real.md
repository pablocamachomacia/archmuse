# PRD — Retranqueos del edificio medido vs. límite real de parcela (OP-18)

**Estado:** Borrador · **Fecha:** 2026-08-20 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Alcance de esta Fase, explícito

Este PRD documenta **OP-18**, decidido por Pablo el 2026-08-20 (`docs/AGENTE_BACKLOG.md` §13.3, entrada "Decidida el 2026-08-20"), marcado en el propio backlog como **"PRÓXIMA, tras cerrar V1"** — no antes. No implementa nada.

Cruza dos geometrías que **ya existen por separado**: la huella del edificio medida (`OP-16`, `superficies.medicion_de_planta`, `analyzer/medicion.py`) y el límite real de parcela de Catastro (Fase A, `docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`, `analyzer/sitio.py`). **No sustituye** el proxy de retranqueos ya existente (`evaluate_retranqueos`, `analyzer/evaluator.py`), que sigue siendo el cálculo aplicable cuando no hay geometría real de parcela disponible. No toca el techo de C4 ni el registro de capacidades (`agente/registro.py`, D-12).

**Dependencia explícita:** OP-18 solo tiene sentido si Fase A (el PRD de procedencia de parcela de hoy) está aprobado — sin eso, la geometría de Catastro que aquí se consume no tiene fecha ni procedencia fiable. Este PRD asume Fase A aprobada; si no lo está, este documento queda en espera de esa aprobación, no se implementa por delante.

## 1. Problema que resuelve

`evaluate_retranqueos` (`analyzer/evaluator.py`) es, por su propio docstring, un **"proxy simple de retranqueos, SIN geometría real de solar"**: resta `2×retranqueos_m` del ancho y del largo del solar, asumiendo un solar rectangular y un retranqueo simétrico en los cuatro lados, a partir de dos escalares (`ancho_m`, `largo_m`) que el arquitecto declara a mano en la entrevista. Si el solar es irregular, la función ni siquiera se ejecuta — devuelve `None`.

Al mismo tiempo, para proyectos ligados a una dirección real, **ya existe** la geometría real de la parcela (`geometria_parcela.coordenadas`, el polígono real de Catastro vía WFS/INSPIRE) y **ya existe** la huella real del edificio medida sobre el DXF (`OP-16`). Nada hoy cruza ambas. Es exactamente el hueco que el título de OP-18 en el backlog nombra: *"¿se retranquea el edificio lo que exige la parcela real?"*

## 2. Usuario afectado

El mismo arquitecto de hoy, evaluando un proyecto sobre una parcela real ya consultada en Catastro (no un usuario nuevo) — extiende un flujo que ya se usa, no abre uno.

## 3. Objetivo de negocio

Un retranqueo calculado sobre un solar rectangular asumido es exactamente el tipo de aproximación que un colegio de arquitectos puede objetar en visado si la parcela real es irregular — que es el caso más frecuente, no la excepción. Sustituirlo por una medición real, cuando la geometría real ya está disponible en el sistema, es la misma lógica de defendibilidad que ya motivó la Fase A de hoy.

## 4. Objetivo técnico

Una vez implementado:

1. Cuando existan ambas geometrías — parcela real (Catastro, Fase A) y huella de edificio medida (OP-16) — para el mismo proyecto, se calcula el retranqueo real **en cada lindero**, no un valor único simétrico.
2. El proxy actual (`evaluate_retranqueos`) sigue funcionando exactamente igual, sin cambios, para los proyectos sin geometría real de parcela — esto es un añadido, no una sustitución.
3. Cuando la comparación no sea posible (geometrías en sistemas de referencia distintos sin resolver, ver §6), el sistema lo dice explícitamente — nunca cae en silencio al proxy antiguo sin decirlo.

## 5. Casos de uso

1. El arquitecto analiza un DXF ligado a una dirección real con parcela consultada en Catastro; ve el retranqueo medido en cada lindero, no un único valor simétrico.
2. La parcela es irregular — hoy `evaluate_retranqueos` ni se ejecuta (devuelve `None`); con OP-18 sí puede evaluarse, porque no depende de reducir la parcela a ancho/largo.
3. El edificio invade el retranqueo mínimo en un lindero concreto (p. ej. el fondo de parcela) pero no en los demás — el hallazgo señala el lindero exacto, no una nota genérica de "retranqueo insuficiente".

## 6. Pregunta abierta — NO decidida en este PRD

**¿Cómo se resuelve el cruce entre la geometría de parcela (lon/lat, de Catastro, en `analyzer/sitio.py`) y la huella del edificio (coordenadas locales del DXF, sin georreferenciar, en `analyzer/medicion.py`)?** No existe hoy en el repositorio ningún mecanismo de transformación entre ambos sistemas de referencia — no es un detalle menor, es el problema técnico central de este PRD. Dos caminos posibles, ninguno decidido aquí:

- **(a) Anclaje manual:** el arquitecto declara un punto y una orientación (el campo `norte_grados`, ya existente en el flujo de análisis, es candidato natural) que vincule el origen del DXF con un punto real de la parcela. Más barato, pero añade un paso a la UX que no existe hoy.
- **(b) Georreferenciación automática:** mucho más cara, probablemente exige una librería de proyección nueva (`pyproj` o equivalente) no presente hoy en `requirements.txt`.

Esto no bloquea la existencia de este PRD, pero sí bloquea cualquier estimación de horas fiable y cualquier trabajo real de implementación hasta que Pablo decida — no se elige aquí porque no es una decisión técnica menor, es un compromiso de UX/alcance que le corresponde a él, no a este documento.

## 7. Flujo del usuario

Sin cambio en la entrada. Se añade un hallazgo nuevo (o se enriquece el existente de retranqueos) en el informe/API, condicionado a que ambas geometrías estén disponibles y resueltas en un sistema de referencia común para el proyecto.

## 8. Criterios de aceptación

1. Cuando ambas geometrías (parcela real + huella medida) están disponibles y resueltas en un sistema de referencia común, el retranqueo se reporta lindero a lindero, con el segmento de parcela concreto del que sale cada cifra.
2. Cuando falta cualquiera de las dos geometrías, o el cruce de referencia no está resuelto (§6), el sistema lo dice explícitamente y no sustituye en silencio con el proxy antiguo sin decirlo.
3. `evaluate_retranqueos` (el proxy actual) sigue funcionando exactamente igual para los proyectos sin geometría real — ningún test existente de `analyzer/evaluator.py` se rompe.
4. Un solar no rectangular, que hoy hace que `evaluate_retranqueos` devuelva `None`, puede evaluarse con OP-18 si el proyecto tiene geometría real de Catastro.

## 9. Riesgos

- **Técnico, alto — el único bloqueante real de este PRD.** Cruzar dos sistemas de referencia geométrica (lon/lat de Catastro vs. coordenadas locales de DXF) no es una extensión trivial de código existente: es una pieza nueva que puede requerir una dependencia nueva (`pyproj` o similar) y que tiene un componente de UX no técnico (§6) que Pablo debe decidir antes de poder estimar en serio.
- **De arquitectura, a decidir en la implementación.** Si la geometría erosionada (offset de polígono con manejo de concavidad) se replica en Python (`analyzer/`) reutilizando el concepto ya escrito en JS para el sólido capaz (`viewer-terreno.js::poligonoAutointersecta`, `docs/prd/2026-08-17-solido-capaz-sandbox.md`) o si se porta con `shapely` — que ya es dependencia del repo (usada en `analyzer/parser.py`), así que el offset en sí es barato una vez resuelto §6, que es lo caro.
- **Techo de C4, respetado.** Este PRD no propone ninguna Capacidad nueva en `agente/registro.py` ni toca D-12 — es una extensión de dos motores de cálculo ya existentes (Catastro/Fase A y medición OP-16), consumida por `evaluator.py` como hoy. Si al implementar resultara necesario tocar el registro de capacidades, es motivo de pausa y pregunta a Pablo, no una decisión de este documento.
- **De negocio, ninguno nuevo.** No compite por las mismas horas que `REFACTOR_MASTERPLAN.md`.

## 10. Impacto sobre módulos existentes

| Fichero | Qué tocaría |
|---|---|
| `analyzer/sitio.py` | Fuente de la geometría real de parcela (`_geometria_parcela_catastro`, Fase A) — solo lectura, sin cambios. |
| `analyzer/medicion.py` | Fuente de la huella de edificio medida (motor de OP-16) — solo lectura, sin cambios. |
| `analyzer/evaluator.py` | `RetranqueosResult` y `evaluate_retranqueos` — el proxy actual se mantiene intacto; el nuevo cálculo con geometría real sería una función nueva, probablemente un `RetranqueosResult` ampliado o un tipo hermano — a decidir al implementar. |
| Módulo nuevo, por decidir (¿`analyzer/georeferencia.py`? ¿ampliación de `sitio.py`?) | Resolución del sistema de referencia común (§6) — no existe hoy, es la pieza central de este PRD y no se ubica en este documento. |
| `app.py` / `analyzer/api_serializer.py` | Wiring del nuevo hallazgo — no se toca en este PRD. |
| `static/index.html`, `static/viewer-sandbox.js` | Posible visualización — `viewer-sandbox.js` ya dibuja la parcela real erosionada por un retranqueo declarado (sólido capaz), así que hay una superficie de reutilización visual candidata, pero no se decide ni se toca aquí. |

## 11. Plan de implementación dividido en pequeñas tareas

Especulativo — se valida y se detalla si Pablo aprueba el PRD:

1. **Decisión con Pablo sobre §6** (anclaje manual vs. georreferenciación automática) — bloqueante, sin estimación de horas porque es una decisión de producto, no una tarea de desarrollo.
2. **Según lo decidido en la tarea 1:** implementar la transformación de referencia (~4-8h según la opción elegida — el rango es tan amplio precisamente porque la tarea 1 no está resuelta).
3. **Función de cálculo de retranqueo real lindero a lindero**, reutilizando el patrón de offset/erosión ya validado en `viewer-terreno.js` (~3h).
4. **Extender `evaluator.py`** con el nuevo resultado, sin tocar `evaluate_retranqueos` existente (~2h).
5. **Wiring a API/serializer**, si aplica (~1h).
6. **Tests** (~2h).

Total estimado: **no cerrado** — depende enteramente de la tarea 1, que es una decisión de Pablo, no un desarrollo. Con la opción (a) del §6 (anclaje manual), el total ronda ~12h; con la opción (b) (georreferenciación automática), es sustancialmente mayor y no se estima aquí sin más detalle de la tarea 1.

## 12. Plan de pruebas

- Nuevo test sobre el cálculo de retranqueo real: parcela sintética no rectangular + huella de edificio sintética, con el retranqueo esperado calculado a mano por lindero.
- Regresión completa de `analyzer/evaluator.py` — `evaluate_retranqueos` debe seguir devolviendo exactamente los mismos valores para los casos que ya cubre hoy.
- Test de caso límite: geometrías sin referencia común resuelta → el sistema declara explícitamente "no evaluable", no falla en silencio ni recurre al proxy sin decirlo.

## 13. Métricas para medir el éxito

No hay una métrica de producto medible a corto plazo — mismo criterio de auditoría que el resto de esta serie: dentro de un mes, un proyecto con parcela real y huella medida disponibles reporta el retranqueo lindero a lindero real, no el proxy simétrico, y lo dice explícitamente cuando no puede.

## 14. Posibles motivos para NO implementar la idea (o recortarla)

- **El backlog ya lo marca "próxima, tras cerrar V1"** — igual que OP-17, no compite por prioridad con lo que falta para cerrar V1.
- **El riesgo técnico central (§6, §9) no es menor.** Sin resolver el cruce de sistemas de referencia, este PRD no tiene una estimación de horas fiable — cualquier aprobación debería ir acompañada de la decisión de §6 primero, no de un "adelante" genérico sobre el documento completo.
- **Recorte honesto posible:** implementar solo la opción (a) de anclaje manual (declarado por el arquitecto), sustancialmente más barata que la georreferenciación automática y suficiente para el caso de uso principal (un proyecto, una parcela, un DXF). Se apunta como recorte razonable, no como recomendación cerrada — es exactamente la pregunta que el §6 deja abierta para Pablo.
- **Motivo de fondo:** OP-18 depende de que Fase A (el PRD de procedencia de parcela de hoy) esté aprobado e implementado primero — sin fecha/procedencia fiable en la geometría de Catastro, cruzarla con la huella del edificio hereda esa misma falta de trazabilidad. No tiene sentido aprobar OP-18 por delante de Fase A.

---

**Decisión:** _pendiente de revisión por Pablo_
