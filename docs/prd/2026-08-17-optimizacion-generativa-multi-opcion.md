# PRD — Optimización Generativa Multi-Opción (3 alternativas + comparador)

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: generar 3 alternativas de distribución (A: viviendas pequeñas, B: equilibrada/familiar, C: máximo m² útil/terrazas) para el mismo Sólido Capaz, con un comparador de métricas y la posibilidad de aplicar la elegida al visor 3D.

A diferencia de los tres PRD anteriores de hoy, este **no choca con ninguna carencia de datos geométricos** — se apoya en generación de IA ya existente (`analyzer/ai_generator.py::generate_project`) y en métricas que, en su mayoría, ya son calculables con datos reales gracias a piezas ya construidas hoy mismo (núcleo de comunicación vertical). Pero tiene dos decisiones de diseño que cambian el resultado y el coste de forma sustancial, y conviene resolverlas antes de programar:

- **"Opción A: maximizar viviendas pequeñas" choca con cómo funciona hoy el generador.** `generate_project` recibe `mix_viviendas` (nº de viviendas por tipología) como **parámetro de entrada fijado por el usuario en el Programa de Necesidades**, no como algo que la IA decide. El generador hoy no elige cuántas viviendas de cada tamaño caben — coloca las que se le piden. Para que "Opción A" signifique de verdad "más viviendas pequeñas" hay que decidir: ¿las 3 opciones comparten el mismo `mix_viviendas` fijo y solo cambian en cómo se reparte el espacio dentro de esa cifra (interpretación débil, siempre disponible hoy), o cada opción genera con un `mix_viviendas` distinto derivado automáticamente del mismo Sólido Capaz (interpretación fuerte, la que probablemente Pablo tiene en mente, pero requiere una función nueva que proponga 3 mixes distintos a partir de la superficie construida objetivo)? Ver §6/§14.
- **Generar 3 alternativas es generar 3 veces con Claude.** `generate_project` ya hace 1-2 llamadas reales a la API (con reintento). Multiplicarlo por 3 significa hasta 6 llamadas por petición del usuario — coste y latencia real, no gratis. Esto debe ser una acción explícita que el usuario pide sabiendo que tarda más y cuesta más (no un botón que se pulsa sin saberlo), con progreso visible por opción.

Lo que sí es directamente reutilizable, verificado en el código:

- El mecanismo de **directivas cualitativas ya existente** (`contexto_cualitativo`, catálogo cerrado `CATEGORIAS_DIRECTIVA_VALIDAS`/`FUERZAS_DIRECTIVA_VALIDAS`, línea 221) es exactamente el canal ya construido y ya seguro (nunca reenvía texto libre del cliente, `ai_generator.py` línea 393-406) para steering distinto por opción — no hace falta inventar un canal de prompt nuevo ni romper la regla de seguridad ya documentada de no aceptar texto arbitrario del cliente.
- **"Repercusión de zonas comunes" ya es un dato real hoy**, gracias al núcleo de comunicación vertical añadido el mismo día (`_dimensionar_nucleo_comunicacion`/`_construir_unidad_nucleo`, PRD `2026-08-17-nucleo-comunicacion-fachada-generador.md`): superficie del núcleo entre superficie construida total, sin inventar nada.
- **"% de fachada aprovechada" no existe como métrica hoy, pero es construible con datos reales**: ya existe detección de fachada exterior por habitación (`evaluator.py`, orientación/ventilación natural) — falta agregar esos resultados en un único ratio (perímetro/fachada con estancia habitable adosada vs. fachada total), función nueva pero sin inventar geometría.
- **"Margen estimado" reutiliza la fórmula ya aprobada e implementada en la pestaña de Viabilidad Económica** (PEM = superficie × ratio, margen = precio venta − PEM − suelo, `static/app.js:3048`) — aplicada a cada una de las 3 opciones con los MISMOS parámetros de usuario (ratio €/m², precio, suelo), nunca un dato de mercado inventado por ArchMuse. Si Pablo prefiere en su lugar el Margen Promotor (%) del PRD de Viabilidad Financiera (`2026-08-17-analisis-de-viabilidad-financiera.md`, aún pendiente de aprobación), este PRD depende de que ese se apruebe primero — por defecto se asume la fórmula ya en producción.
- **"Balance de tipologías"** ya es el `mix_viviendas`/Programa de Necesidades existente — dato directo, sin cálculo nuevo.
- **Terrazas ya son un tipo de estancia que el generador coloca** (`ai_generator.py:597`, zona sur salón/cocina + terraza/tendedero) — "maximizar terrazas" es una instrucción de steering razonable dentro de lo que el generador ya sabe hacer, no una capacidad nueva de geometría.

## 1. Problema que resuelve

Hoy el arquitecto genera una única distribución por Sólido Capaz y no tiene forma de comparar alternativas de diseño (más viviendas pequeñas vs. familiar vs. maximizar superficie/terrazas) sin regenerar manualmente y perder la anterior — no hay comparación lado a lado ni forma de decidir con datos entre varias propuestas.

## 2. Usuario afectado

El arquitecto (o el promotor con él) en la fase de anteproyecto, decidiendo el enfoque de producto de un edificio antes de comprometerse a una distribución concreta.

## 3. Objetivo de negocio

Es el pilar de "asesor de decisiones", no solo generador, de `NORTH_STAR_2031.md` — comparar opciones con métricas reales en vez de solo generar una vez es un salto de valor genuino. El riesgo de `DESTROY_ARCHMUSE.md` aquí es menor que en los PRD anteriores de hoy (no hay dato inventado de por medio si se implementa como se describe), pero sí hay riesgo de coste: 3-6 llamadas a Claude por petición es un coste variable real que debe ser una decisión consciente del usuario, no automática.

## 4. Objetivo técnico

- `analyzer/ai_generator.py`: nueva función `generate_project_opciones(params, perfiles=["A","B","C"], model=MODEL) -> Dict[str, GeneratedProject]` que llama a `generate_project` una vez por perfil, inyectando una directiva cualitativa blanda predefinida y validada por perfil (usando el catálogo cerrado ya existente, no texto libre) y, si se aprueba la interpretación fuerte de §0, un `mix_viviendas` derivado distinto por perfil.
- Nuevo módulo `analyzer/comparador_opciones.py` (o funciones dentro de `ai_generator.py`): calcula, para cada `GeneratedProject`, las 4 métricas del comparador — repercusión de zonas comunes (real), % fachada aprovechada (real, nueva), margen estimado (real, con parámetros del usuario), balance de tipologías (real, ya existente) — sin tocar `evaluator.py` salvo para reutilizar sus resultados de fachada/orientación ya calculados.
- UI: tabla comparativa de 3 columnas + botón "Aplicar esta opción al edificio" que sustituye el proyecto activo del visor 3D por la opción elegida (reutilizando el mecanismo ya existente de aceptar/guardar un `GeneratedProject`).

## 5. Casos de uso

1. Arquitecto con un Sólido Capaz y Programa de Necesidades ya resueltos pulsa "Generar 3 opciones" → ve progreso por opción (A, B, C) mientras se generan secuencialmente, y al terminar, un comparador con las 3 columnas y sus 4 métricas.
2. Arquitecto compara y ve que la Opción C tiene mejor % de fachada aprovechada pero peor repercusión de zonas comunes → decide con datos, no a ojo.
3. Arquitecto pulsa "Aplicar" sobre la Opción B → el visor 3D del edificio completo pasa a mostrar esa distribución, descartando (o guardando aparte, a decidir) las otras dos.

## 6. Casos límite

- **Alguna de las 3 generaciones falla** (`GenerationError`, timeout, o `advertencias` graves tras el reintento): el comparador debe poder mostrar 2 de 3 opciones con la tercera marcada como "no generada" y un botón para reintentar solo esa, no descartar las que sí funcionaron.
- **Las 3 opciones generan geometría muy similar** (Claude no diferencia lo suficiente el steering blando): caso real y probable al principio — el comparador debe mostrarlo igualmente (mismos números, sin forzar diferencia artificial); si esto ocurre sistemáticamente en pruebas, es una señal de que el steering necesita ser más explícito (posiblemente `mix_viviendas` distinto de verdad, no solo directiva de estilo — ver §0).
- **`mix_viviendas` no permite 3 variaciones razonables** (p. ej. Programa de Necesidades pide solo 2 viviendas totales — no hay margen para "más pequeñas" vs "más grandes" con sentido): el sistema debe poder generar menos de 3 opciones distintas y decirlo, no inventar una diferencia donde no la hay.
- **Usuario pulsa "Generar 3 opciones" repetidamente**: cada pulsación cuesta 3-6 llamadas a Claude — debe haber un aviso de coste/tiempo antes de lanzar, y deshabilitar el botón mientras una generación está en curso.
- **Ninguna opción se aplica nunca**: el proyecto activo no debe cambiar solo por haber generado opciones — aplicar es un paso explícito y separado (mismo criterio que "generar plantas con IA" ya usa hoy: generar no sustituye nada hasta que el usuario confirma).

## 7. Flujo del usuario

1. Arquitecto con Sólido Capaz + Programa de Necesidades resueltos entra en el modo "Optimización Generativa Multi-Opción".
2. Ve un aviso de coste/tiempo ("esto genera 3 propuestas distintas, puede tardar más que generar una sola") y confirma.
3. Ve progreso por opción (A/B/C) mientras se generan secuencialmente.
4. Ve el comparador con las 3 columnas y sus 4 métricas, cada una con badge de "estimación tuya" donde aplique (margen estimado).
5. Pulsa "Aplicar esta opción" sobre la que prefiere → el visor 3D del edificio completo se actualiza con esa distribución.

## 8. Criterios de aceptación

1. Cada una de las 3 opciones es un `GeneratedProject` real, generado por una llamada independiente a `generate_project` (o su reintento), nunca una variación cosmética de un único resultado.
2. La repercusión de zonas comunes mostrada coincide con superficie del núcleo de comunicación / superficie construida total de esa opción — verificable con los mismos números que ya expone el resto de la app para esa unidad.
3. El % de fachada aprovechada se calcula reutilizando los resultados ya existentes de `evaluator.py` (orientación/ventilación), no una detección de fachada paralela.
4. Ningún "margen estimado" aparece sin que el usuario haya introducido ratio/precio/suelo — mismo criterio que la pestaña de Viabilidad Económica, badge de estimación propia incluido.
5. Aplicar una opción sustituye el proyecto activo del visor solo tras una acción explícita del usuario — nunca automáticamente al terminar de generar.
6. Si una de las 3 generaciones falla, las otras 2 siguen mostrándose y son aplicables igualmente.

## 9. Riesgos

- **Coste y latencia real**: hasta 6 llamadas a Claude por petición del usuario. Mitigar con aviso explícito antes de lanzar y, si el coste resulta alto en uso real, considerar limitar a 2 opciones por defecto con la tercera opcional.
- **Riesgo de que el steering sea insuficiente** (Opción A/B/C terminen pareciéndose demasiado) si se implementa solo con directiva cualitativa blanda sin variar `mix_viviendas` — ver la decisión de interpretación fuerte/débil en §0, es el riesgo de producto más relevante de este PRD (que el usuario no perciba diferencia real entre las 3 y sienta que pagó 3x por nada).
- **Complejidad de estado en el frontend**: mantener 3 `GeneratedProject` en memoria simultáneamente, con progreso independiente y posibilidad de reintento parcial, es más estado del que maneja hoy el flujo de generación única — revisar que no colisione con el estado ya existente de Sandbox/Programa de Necesidades.
- Compite por tiempo con `REFACTOR_MASTERPLAN.md` y con el resto de PRD en cola hoy.

## 10. Impacto sobre módulos existentes

- `analyzer/ai_generator.py`: nueva función `generate_project_opciones`, reutilizando `generate_project` sin modificarla.
- **Nuevo** `analyzer/comparador_opciones.py`: cálculo puro de las 4 métricas por opción, a partir de `GeneratedProject` + resultados ya existentes de `evaluator.py` + parámetros de usuario para margen.
- `app.py`: nuevo endpoint (p. ej. `POST /api/generar-opciones`) que orquesta las 3 llamadas y devuelve el comparador — decidir si es síncrono (el usuario espera las 3) o si conviene streaming/polling dado el tiempo total (a definir en plan de implementación, no asumido aquí).
- `static/`: nueva UI del comparador + reutilización del mecanismo ya existente de "aplicar/aceptar proyecto generado" al visor 3D del edificio completo (`viewer-edificio.js`).
- Ningún cambio en `evaluator.py` salvo, si hace falta, exponer como función pública algún resultado de fachada que hoy sea interno.

## 11. Plan de implementación dividido en pequeñas tareas

1. Decisión previa con Pablo: interpretación fuerte o débil de "Opción A/B/C" (§0/§6) — bloqueante para el resto.
2. `ai_generator.py`: `generate_project_opciones` con las 3 directivas cualitativas predefinidas (catálogo cerrado ya existente) y, si aplica interpretación fuerte, la función que deriva 3 `mix_viviendas` distintos desde el mismo total.
3. `analyzer/comparador_opciones.py`: repercusión de zonas comunes + balance de tipologías (triviales, datos ya existentes).
4. `analyzer/comparador_opciones.py`: % de fachada aprovechada (nueva agregación sobre resultados ya existentes de `evaluator.py`).
5. `analyzer/comparador_opciones.py`: margen estimado, reutilizando la fórmula ya en producción de Viabilidad Económica.
6. `app.py`: endpoint de orquestación de las 3 generaciones + comparador.
7. UI: aviso de coste/tiempo + progreso por opción + tabla comparativa.
8. UI: botón "Aplicar esta opción" conectado al mecanismo ya existente de proyecto activo del visor 3D.
9. Verificación: los 6 criterios de §8, incluyendo el caso de fallo parcial (§6) con un proyecto de prueba real.

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/ai_generator.py analyzer/comparador_opciones.py`.
- `tests/test_comparador_opciones.py`: las 4 métricas con datos sintéticos (`GeneratedProject` de prueba), incluyendo el caso de fallo parcial.
- En vivo: generar 3 opciones sobre el mismo proyecto de prueba ya usado en sesiones anteriores (Sandbox, mix 20/60/20/0), confirmar que el comparador muestra las 3 con métricas coherentes y que "Aplicar" sustituye correctamente el proyecto activo del visor.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que las 3 opciones se perciben como genuinamente distintas (no ruido aleatorio del mismo mix), y que ninguna métrica del comparador podría confundirse con un dato de mercado real de ArchMuse.

## 14. Posibles motivos para NO implementar la idea (o para recortar el alcance)

- **Si se implementa solo con directiva cualitativa blanda (interpretación débil de §0) sin variar `mix_viviendas`, el valor real del comparador puede ser bajo** — las 3 opciones podrían no diferenciarse lo suficiente para justificar 3x el coste/tiempo. Recomiendo que la interpretación fuerte (variar `mix_viviendas` de forma derivada y automática) sea la aprobada, aunque exige una función nueva (proponer 3 repartos de tipología distintos desde el mismo total de superficie construida objetivo) que no existe hoy.
- **El coste de 3-6 llamadas a Claude por petición no es trivial a escala** — si el volumen de uso de "generar opciones" resulta alto, esto puede convertirse en el mayor coste variable de la aplicación de un plumazo. Vale la pena empezar con 2 opciones (A/B o B/C, a elegir por el usuario) en vez de 3 fijas, y ampliar a 3 solo si el coste observado lo permite.
- **"Margen estimado" hereda toda la limitación ya señalada en el PRD de Viabilidad Económica**: sin ratio de mercado real, es una calculadora que compara 3 números que el propio usuario alimentó igual en los 3 casos — útil para comparar entre opciones (ceteris paribus), no como validación de viabilidad real de ninguna de ellas. Esto es honesto de decir en la UI, no solo en este documento.
- Si Pablo confirma la interpretación fuerte de las 3 opciones y acepta el coste de 3x llamadas a Claude (o el recorte a 2 opciones), este PRD es implementable en el alcance descrito, apoyado casi enteramente en piezas ya existentes.

---

**Decisión:** **Aprobado (2026-08-17)**. Interpretación **fuerte** de §0/§14: 2 opciones (no 3), cada una con un `mix_viviendas` distinto derivado automáticamente del mismo total de superficie construida objetivo — no solo variación de estilo con el mismo mix. Reduce el coste de hasta 6 llamadas a Claude a hasta 4.
