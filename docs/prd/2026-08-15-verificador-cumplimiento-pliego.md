# PRD — Verificador de cumplimiento de pliego

**Estado:** Aprobado e implementado · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-15)

---

## 0. Relación con el otro PRD pendiente

`docs/prd/2026-08-15-conector-pliego-generador.md` (todavía sin aprobar) proponía en su §11 tareas 7-8 una sección de informe "Cumplimiento del pliego" construida sobre comprobaciones nuevas de `evaluator.py`. Este PRD es esa misma pieza, pero **desacoplada y más general**: verifica CUALQUIER proyecto (analizado desde un DXF real o generado con IA) contra CUALQUIER pliego importado, sin depender de que el proyecto se haya generado a partir de ese pliego. Si se aprueban los dos, el conector debería consumir este módulo en vez de reimplementar sus propias comprobaciones — se deja anotado aquí para no duplicar trabajo cuando llegue ese momento.

## 1. Problema que resuelve

El extractor de pliegos (aprobado e implementado hoy) dice qué exige el concurso; nada en ArchMuse dice todavía si un proyecto concreto lo cumple. Hoy el arquitecto tiene que comparar a ojo la tabla de revisión del pliego contra el informe del proyecto — exactamente el tipo de comprobación mecánica y propensa a error que ArchMuse ya automatiza para la normativa CTE (`evaluator.py`, ~40 reglas). Encargo directo de Pablo (2026-08-15).

## 2. Usuario afectado

El mismo arquitecto de los dos PRDs de pliegos anteriores, en el momento de decidir si un proyecto (propio, analizado o generado) es presentable a un concurso concreto — antes de invertir más tiempo afinándolo o de presentarlo y arriesgarse a quedar excluido por un incumplimiento administrativo.

## 3. Objetivo de negocio

Es la pieza que convierte "ArchMuse sabe leer un pliego" en "ArchMuse te dice si vas a quedar excluido del concurso antes de presentarlo" — mucho más cerca del "evita el coste de un rechazo" que `MOAT_ANALYSIS.md` (línea 16) ya identifica como el valor real del producto, y más concreto que el propio extractor (que solo lee, no juzga).

## 4. Objetivo técnico

- Dado un proyecto (analizado o generado) y un pliego ya extraído, producir una comprobación **determinista, 100% software, sin ninguna llamada a Claude** — encaja directamente con la filosofía de Pablo del 2026-08-01 ("que use software al máximo y IA lo mínimo"): todos los datos ya existen estructurados a ambos lados (el pliego como `Hecho`, el proyecto como JSON serializado), esto es aritmética y comparación, no interpretación.
- Cada comprobación se clasifica en exactamente tres estados, nunca dos: `cumple` / `no_cumple` / **no verificable** — un parámetro que el pliego no citó (`no_encontrado`) o que ArchMuse no puede calcular hoy (ver §6, dos casos reales) nunca se presenta como "cumple" por omisión.
- `blockers` son solo los incumplimientos marcados `critico=True` — una clasificación explícita, propuesta por ArchMuse y confirmable por Pablo (§9), no inferida del texto del pliego.
- El `score_cumplimiento` nunca se calcula sobre comprobaciones `no_verificable` — no se premia ni penaliza al proyecto por algo que ArchMuse no pudo comprobar.

## 5. Casos de uso

1. **Proyecto generado con pliego de fondo** (aunque el conector del otro PRD no exista todavía): el arquitecto generó libremente, importó el pliego por separado, y pide "verificar contra este pliego" — el caso más común hasta que el conector exista.
2. **Proyecto analizado desde un DXF real** de un estudio, contra un pliego de un concurso al que se plantean presentarlo — sin que el DXF tenga ninguna relación previa con ese pliego.
3. **Verificación repetida** tras ajustar el proyecto (cambiar mix de viviendas, reducir plantas): se vuelve a pedir sobre el mismo proyecto ya guardado, sin volver a subir nada.

## 6. Casos límite

- **Un parámetro del pliego es `UNKNOWN`** (no citado): el check correspondiente es `no_verificable`, `valor_exigido=null`, nunca se cuenta como incumplimiento ni como cumplimiento.
- **`pem_maximo_euros` — no implementable tal como está especificado.** El encargo pide "usar ratio €/m² construido del pliego", pero el extractor de pliegos (17 campos ya aprobados) no extrae ningún €/m² — solo `pem_maximo_euros` (un tope total) y `ratio_construido_util_max` (una relación de superficies, no monetaria). ArchMuse tampoco calcula un coste de construcción en ningún sitio hoy (`chain_effects.py` solo tiene tres cubos "Bajo/Medio/Alto" para problemas puntuales, no una tasa €/m²). Este check sale siempre `no_verificable` con motivo explícito, salvo que se apruebe también extender el extractor con un campo nuevo (p. ej. `precio_maximo_licitacion_m2`) — decisión de Pablo, no asumida aquí (ver §9).
- **`porcentaje_accesibilidad` — aproximación semántica, no una medida literal.** Lo único que ArchMuse calcula hoy relacionado con accesibilidad es, por vivienda, si su baño pasa `evaluate_bathroom_accessibility`/`evaluate_accessible_bathroom_area` (giro + superficie mínima) — no si toda la vivienda es "adaptada" en el sentido que suele exigir un pliego de VPP. Este check usa "% de viviendas con baño accesible" como proxy, etiquetado explícitamente como aproximación en `motivo` — nunca se presenta como una medida exacta de lo que pide el pliego.
- **Edificabilidad/superficie del solar no están en el JSON del proyecto hoy.** `analyzer/api_serializer.py::serialize_analysis` calcula `edificabilidad_real` (`evaluator.py::evaluate_buildability`) pero solo lo vuelca como texto dentro de `problemas_edificio` (una lista de strings), nunca como número estructurado — y `solar` ni siquiera se incluye en el JSON devuelto, pese a recibirse como parámetro. Este PRD necesita una extensión pequeña y aditiva de `serialize_analysis` (bloque `"urbanismo"` nuevo con los números, no solo el mensaje) — no un cálculo nuevo, el número ya se calcula, solo no se expone. Sin este dato, la comprobación de edificabilidad es `no_verificable` (caso normal en un DXF analizado, que no declara solar).
- **`mix_tipologias` del pliego usa texto libre para "tipo"** (p. ej. "2 dormitorios", "vivienda de 3 hab."), y el proyecto no tiene un campo "tipología" por vivienda — solo habitaciones con nombre. Hace falta una función determinista que bucketice cada vivienda por nº de dormitorios (contando habitaciones "Dormitorio N", ya con nomenclatura obligatoria en `ai_generator.SYSTEM_PROMPT`, y heurística equivalente para un DXF analizado) antes de poder comparar contra el pliego — ver §11.
- **Ni proyecto ni pliego existen, o el id no tiene forma válida**: 404, mismo criterio que el resto de `app.py`.

## 7. Flujo del usuario

1. Desde la vista de un proyecto (analizado o generado), el arquitecto elige "Verificar contra un pliego" y selecciona uno de sus pliegos ya importados (hace falta un listado — ver Riesgos, `GET /api/pliegos` no existe todavía).
2. ArchMuse llama a `GET /api/proyectos/<id>/verificar-pliego/<pliego_id>`.
3. El panel "Verificación de concurso" muestra: un semáforo por parámetro (verde=cumple, rojo=no cumple, gris=no verificable), los `blockers` destacados arriba con explicación en lenguaje llano, y el `resumen_ejecutivo`.
4. Si hay `blockers`, se comunican como lo que son — motivo probable de exclusión del concurso — no como una advertencia más entre otras.

## 8. Criterios de aceptación

- Los 7 checks pedidos existen todos, cada uno con `no_verificable` como resultado honesto cuando falta el dato de origen (pliego o proyecto) — nunca un `cumple`/`no_cumple` inventado.
- `pem` sale `no_verificable` en el 100% de los casos con el extractor actual (documentado, no un bug).
- `mix_tipologias` con ±5% de tolerancia: un proyecto en el límite exacto (p. ej. pide 60% y el proyecto tiene 65%) cumple; a 65,01% no.
- `score_cumplimiento` nunca baja por un check `no_verificable`; dos proyectos idénticos salvo que a uno le falta un dato de pliego no verificable puntúan igual.
- Un `blocker` real (p. ej. `num_viviendas` por debajo del mínimo) aparece siempre en `blockers`, nunca solo en `warnings`.
- El panel del frontend distingue visualmente los tres estados (no solo verde/rojo) — un check gris no se confunde con un check rojo.

## 9. Riesgos

- **La clasificación crítico/no-crítico por defecto es una opinión de producto, no un hecho del pliego.** Propuesta para esta implementación (a confirmar por Pablo al aprobar, no asumida en firme):
  - **Críticos** (van a `blockers`): `num_viviendas_minimo`, `edificabilidad_maxima_m2`, `porcentaje_accesibilidad` — típicamente motivos legales/administrativos de exclusión directa.
  - **No críticos** (van a `warnings`): `mix_tipologias`, `superficie_util` por tipología, `ratio_construido_util_max` — habitualmente penalizan en la baremación, no excluyen.
  - `pem_maximo_euros`: no aplica (siempre `no_verificable`, ver §6).
  Un pliego real puede invertir cualquiera de estas — esta clasificación es un punto de partida razonable, no una regla universal, y debería poder ajustarse sin tocar código si en el futuro varía mucho de un concurso a otro (fuera de alcance de este PRD, anotado como deuda aceptada).
- **`GET /api/pliegos` (listar) no existe.** El extractor solo implementó `GET /api/pliegos/<id>` (uno a uno) porque el flujo de esa fase no necesitaba un listado. El panel de este PRD sí lo necesita para que el arquitecto elija contra qué pliego verificar — endpoint pequeño, mismo patrón que `listar_proyectos`, pero es trabajo real no contemplado en el PRD del extractor.
- **Depende de una extensión pequeña de `serialize_analysis`** (bloque `"urbanismo"` estructurado) — bajo riesgo (aditivo, no cambia ningún campo existente) pero toca un serializador central usado por `/api/analizar` Y `/api/generar`; necesita pasar `tests/test_golden_api_analizar.py` sin diferencias.
- **No compite con `REFACTOR_MASTERPLAN.md`** — módulo nuevo, autocontenido.
- **Puede quedar parcialmente redundante si se aprueba también el conector** (`2026-08-15-conector-pliego-generador.md`) — mitigado por el diseño de §0 (el conector debería reutilizar este módulo, no reimplementarlo).

## 10. Impacto sobre módulos existentes

- **`analyzer/pliego_verificador.py`** (nuevo): `verificar_cumplimiento(proyecto, pliego_json) -> VerificacionPliego`, `CheckCumplimiento`, `VerificacionPliego` — sin dependencia de `anthropic`, ninguna llamada de red.
- **`analyzer/api_serializer.py`**: `serialize_analysis` gana un bloque `"urbanismo"` estructurado (superficie de solar, edificabilidad real/máxima) — aditivo, no cambia ninguna clave existente. Necesita también un helper para bucketizar viviendas por nº de dormitorios (nuevo, pequeño).
- **`analyzer/storage.py`**: sin esquema nuevo. Se añade `listar_pliegos()` (mismo patrón que `listar_proyectos()`) para el selector del frontend.
- **`app.py`**: rutas nuevas `GET /api/proyectos/<proyecto_id>/verificar-pliego/<pliego_id>` (plural "proyectos", no singular como en el encargo — consistencia con el resto de la API) y `GET /api/pliegos`.
- **`static/app.js`**: panel nuevo "Verificación de concurso" en la vista de proyecto (probablemente un modo más de `renderInspector`, mismo patrón que `modoDiagnosticoHtml`).
- **No toca** `evaluator.py` (reutiliza `evaluate_buildability`/`evaluate_bathroom_accessibility` ya existentes, sin duplicarlos) ni `ai_generator.py`.

## 11. Plan de implementación dividido en pequeñas tareas

1. `serialize_analysis`: bloque `"urbanismo"` estructurado (superficie_solar_m2, edificabilidad_real, edificabilidad_maxima) — aditivo, verificar golden test.
2. Función determinista de bucketización por nº de dormitorios (para comparar contra `mix_tipologias` del pliego).
3. `analyzer/pliego_verificador.py`: los 4 checks simples (num_viviendas, edificabilidad, ratio_construido_util, y el proxy de accesibilidad).
4. `analyzer/pliego_verificador.py`: check de `mix_tipologias` (bucketización + tolerancia ±5%) y de `superficie_util` por tipología.
5. `pem_maximo_euros` como `no_verificable` permanente, con motivo explícito — sin lógica de cálculo (no hay dato de origen).
6. `score_cumplimiento` + `resumen_ejecutivo` (plantilla determinista, sin IA).
7. `storage.listar_pliegos()`.
8. `GET /api/pliegos`, `GET /api/proyectos/<id>/verificar-pliego/<pliego_id>` en `app.py`.
9. Panel "Verificación de concurso" en `static/app.js` — semáforo, blockers destacados.
10. Tests deterministas de `verificar_cumplimiento` con proyectos/pliegos sintéticos (sin IA, sin red).

## 12. Plan de pruebas

- Tests unitarios de `verificar_cumplimiento` con combinaciones sintéticas: todo cumple, un blocker, solo warnings, pliego con campos `UNKNOWN`, proyecto sin datos de solar (DXF analizado).
- Test específico de la tolerancia ±5% de `mix_tipologias` en el límite exacto.
- Test de que `pem_maximo_euros` sale `no_verificable` siempre, con el motivo esperado.
- Regresión: `tests/test_golden_api_analizar.py` sigue idéntico tras el bloque `"urbanismo"` nuevo (aditivo).
- Sin ninguna llamada real a Claude en ningún test — el módulo entero es determinista.

## 13. Métricas para medir el éxito

- % de checks que salen `no_verificable` de media, sobre pliegos reales (mide cuánta cobertura real tiene el verificador hoy, no solo en teoría).
- Nº de veces que se pide una verificación por proyecto (proxy de si el arquitecto confía en el panel lo suficiente como para volver a pedirlo tras ajustar el proyecto).
- Casos donde un `blocker` señalado por ArchMuse coincide con un motivo de exclusión real reportado después por el arquitecto (difícil de medir automáticamente, pero es la validación que de verdad importa a medio plazo).

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **El check de PEM, tal como se especificó, no se puede construir con los datos que ArchMuse tiene hoy** — implementarlo iría contra la regla explícita del encargo ("nunca inventar valores") si se rellenara con una tasa €/m² inventada. La alternativa honesta (dejarlo siempre `no_verificable`) cumple la letra del PRD pero no la expectativa real de quien lo pidió; vale la pena decidir explícitamente si se pospone hasta que el extractor tenga un campo de tasa monetaria, en vez de entregarlo "hecho" pero mudo.
- **Depende de una extensión de `serialize_analysis` que no estaba prevista en ningún PRD anterior** — pequeña, pero es la primera vez que este PRD toca ese serializador central fuera del trabajo ya aprobado; vale la pena que Pablo la vea explícitamente antes de tocarla, no solo como una línea del plan.
- **Alternativa más barata**: implementar solo los 4 checks realmente sólidos hoy (num_viviendas, mix_tipologias, edificabilidad para proyectos generados, ratio_construido_util) y dejar accesibilidad y PEM fuera de esta primera versión — con el panel mostrando claramente "2 de 7 comprobaciones pedidas, todavía no implementadas" en vez de forzarlas todas a `no_verificable` desde el primer día. Se deja como alternativa, no como recomendación por defecto: mi lectura es que `no_verificable` explícito ya comunica lo mismo con menos superficie nueva de código, pero es una decisión de Pablo, no mía.

---

**Decisión:** Aprobado por Pablo (2026-08-15), con la clasificación crítico/no-crítico y la decisión de PEM del §9 aceptadas tal cual venían propuestas. Implementado el mismo día: `analyzer/pliego_verificador.py` (7 checks, determinista, sin IA), extensión aditiva de `analyzer/api_serializer.py` (bloques `"urbanismo"` por proyecto y `"accesibilidad"` por vivienda — golden G6/G8 recapturados y revisados a mano), `storage.listar_pliegos()`, rutas `GET /api/pliegos` y `GET /api/proyectos/<id>/verificar-pliego/<pliego_id>`, modo "Concurso" en `static/app.js` con semáforo por check y blockers destacados.
