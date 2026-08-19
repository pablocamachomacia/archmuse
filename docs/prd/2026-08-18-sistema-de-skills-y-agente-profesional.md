# PRD — Sistema de Skills y núcleo agéntico profesional

**Estado:** Borrador · **Fecha:** 2026-08-18 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

**Alcance de este PRD:** la capa que convierte el bucle de herramientas construido hoy (`agente/`) en un sistema agéntico profesional: Skills de primer nivel, memoria de proyecto, verificación, aprobación de efectos, trazabilidad y reanudación. **No** cubre las capacidades de dominio concretas (memorias justificativas, planos de carpintería, revisión BIM): cada una será su propia Skill y, si toca decisiones de producto, su propio PRD.

---

## 1. Problema que resuelve

Petición directa de Pablo (2026-08-18): *«ArchMuse debe entender la intención, analizar el contexto, decidir qué necesita, utilizar Skills y Tools, verificar los resultados y entregar trabajo profesional útil. No quiero un chatbot con herramientas pegadas.»*

Hoy el repositorio tiene lo de abajo y lo de arriba, y nada en medio:

- **Abajo**: 3.777 líneas de motor normativo determinista, un modelo de proyecto con procedencia epistémica, geometría probada contra planos reales, exportación IFC/DXF/glTF, y —desde hoy— un registro de capacidades con manifiesto ejecutable y un bucle de herramientas.
- **Arriba**: la promesa de un copiloto al que se le dice «prepárame la memoria justificativa».

Lo que falta en medio es **el procedimiento profesional**. Una herramienta sabe calcular una superficie; nadie sabe *qué hace un arquitecto* para revisar un proyecto: en qué orden, con qué comprobaciones, qué entrega, qué mira antes de dar algo por bueno. Ese conocimiento existe hoy en tres sitios y ninguno sirve: en la cabeza de Pablo, en 382 líneas de `if/elif` en `classify_problems`, y en prompts largos dentro de `analyzer/ai_analyst.py`.

Un prompt largo no es una Skill. No se puede versionar sin romper proyectos anteriores, no declara qué necesita para funcionar, no dice qué produce, no se puede verificar y no se puede componer con otro. **Este PRD existe para que el conocimiento profesional sea un objeto de primera clase del sistema y no texto dentro de una cadena.**

## 2. Usuario afectado

- **Directo hoy:** el arquitecto de estudio pequeño que ya usa ArchMuse para analizar plantas y que, con esto, puede pedir un trabajo completo en vez de una función.
- **Directo mañana:** el estudio con equipo, donde una Skill es *el procedimiento de la casa* y su valor está en que lo aplique igual el socio que el becario.
- **Indirecto y decisivo:** el curador normativo colegiado, porque una Skill es el sitio donde su corpus se convierte en trabajo entregable.
- **No es para:** el promotor ni el inversor. Las capacidades de viabilidad ya existen y no dependen de esto.

## 3. Objetivo de negocio

Tres, por orden de importancia:

1. **Convertir el foso en producto vendible.** `MOAT_ANALYSIS.md` sitúa el foso en la trazabilidad y en el conocimiento normativo estructurado, no en el visor 3D. Una Skill entrega ese foso en forma de trabajo terminado con acta: es la diferencia entre «una herramienta con IA» y «un colaborador que justifica lo que hizo».
2. **Hacer que el coste de una capacidad nueva tienda a cero.** Hoy cada funcionalidad es una ruta HTTP, una pantalla y una rama en un `if/elif`. Con Skills descubribles, una capacidad nueva es un fichero. Es lo que separa un producto con doce funciones de uno con doscientas.
3. **Abrir la vía de distribución.** Una Skill declarada es exportable como servidor MCP y como complemento de Revit sin reescribirla. Sin esa frontera, cada canal nuevo es un producto nuevo.

## 4. Objetivo técnico

Una vez implementado, debe ser cierto, de forma observable:

1. Una Skill se **declara** en un fichero, se **descubre** sin tocar ningún registro central, y lleva `id`, `version` (semver), `requisitos`, `capacidades_que_usa`, `produce` y `verificaciones`.
2. El agente **elige** Skills por su declaración, no por un `if` sobre el texto del usuario.
3. Una Skill **no puede ejecutarse** si sus requisitos no están satisfechos en la memoria del proyecto: el sistema **pregunta** en vez de suponer.
4. Toda salida de una Skill lleva su **naturaleza epistémica** —hecho, cálculo, inferencia o propuesta— y no se puede emitir una sin ella.
5. Ninguna Skill puede aplicar un **efecto** declarado (escribir un fichero del cliente, gastar dinero, llamar a un tercero) sin una autorización explícita para ese efecto.
6. Toda ejecución deja un **acta** con cada paso, su versión, su entrada, su salida y lo que **no** comprobó — derivado, no redactado.
7. Una ejecución interrumpida **se reanuda** sin repetir los pasos ya sellados.
8. Un paso que falla **no aborta el trabajo**: las ramas independientes continúan y el resultado dice qué quedó sin hacer y por qué.
9. Una Skill nueva **no rompe** ejecuciones anteriores: los planes guardados fijan la versión que usaron.
10. El agente puede **detectar que le falta una Skill** y proponer su declaración, y **no puede instalarla por su cuenta**.

## 5. Casos de uso

**CU-1 — Objetivo compuesto.** «Comprueba esta parcela y su normativa.» El agente resuelve el ámbito territorial (Tool), obtiene la normativa aplicable (Tool), detecta que faltan datos del proyecto para evaluar tres reglas, los pide, y entrega una ficha con lo comprobado, lo no comprobado y la cita de cada cifra.

**CU-2 — Requisito insatisfecho.** «Prepárame la memoria justificativa.» La Skill declara que requiere uso, tipología y municipio como `KNOWN`. La memoria del proyecto tiene municipio pero no tipología. El agente **no redacta**: pregunta exactamente por la tipología, y al obtenerla continúa desde donde estaba.

**CU-3 — Efecto que exige aprobación.** Una Skill de documentación va a escribir sobre el DXF del cliente. El sistema se detiene, describe el efecto —qué fichero, qué celdas, que el original no se toca— y espera autorización. Sin ella, entrega el resultado en un fichero nuevo.

**CU-4 — Rama que no se puede ejecutar.** De cinco comprobaciones de una revisión, una depende de una materia sin cobertura en el corpus. Las otras cuatro se ejecutan; el informe declara la quinta como no comprobada, con motivo, y no como cumplida.

**CU-5 — Skill que no existe.** «Hazme los planos de carpintería.» No hay Skill. El agente lo dice, propone una declaración —qué requeriría, qué Tools usaría, qué verificaciones tendría— y la deja como propuesta para revisión humana. No improvisa el trabajo.

**CU-6 — Evolución sin romper.** La Skill de revisión pasa de 1.2.0 a 2.0.0 con una comprobación nueva. Un proyecto revisado hace seis meses sigue reproduciendo su informe con 1.2.0, porque el acta fija la versión.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Dos Skills declaran el mismo `id` | Fallo al descubrir, con las dos rutas. Nunca «gana la última» |
| Una Skill declara una capacidad que no existe | Se rechaza al cargarse, no al ejecutarse |
| Verificación que falla | El resultado se marca **no verificado** y no se entrega como bueno. No se reintenta en bucle |
| El modelo pide una Skill por un nombre parecido | Rechazo tipado. Nunca la más parecida |
| Requisito satisfecho pero con estado `ESTIMATED` | Cuenta como insatisfecho: la Skill exige `KNOWN` salvo que declare lo contrario |
| Ejecución interrumpida a mitad de un paso con efecto | Al reanudar, el paso con efecto **no** se repite sin volver a autorizar |
| Memoria de proyecto con dos valores contradictorios para el mismo requisito | Los dos se conservan con su procedencia; manda el más reciente y el conflicto se declara |
| Skill sin verificaciones declaradas | Se admite, pero su salida se marca como no verificable. No se finge una comprobación |

## 7. Flujo del usuario

1. El arquitecto abre un proyecto y escribe un objetivo en lenguaje natural.
2. ArchMuse muestra **qué va a hacer**: Skills elegidas con su versión, Tools que se ejecutarán, datos que le faltan y efectos que necesitarán aprobación.
3. Si falta un dato, lo pregunta —una pregunta concreta, no un formulario— y lo guarda en la memoria del proyecto con su procedencia.
4. Ejecuta, mostrando el avance paso a paso.
5. Ante un efecto declarado, se detiene y pide autorización con el detalle exacto.
6. Verifica su propio resultado y marca lo que no ha podido verificar.
7. Entrega el trabajo **más el acta**: de dónde salió cada dato, qué no se comprobó, qué quedó pendiente. Todo entregable sale marcado como borrador para revisión de un colegiado.

## 8. Criterios de aceptación

1. Dejar un fichero de Skill en el árbol la hace visible sin tocar ningún `__init__.py`, y un test lo comprueba en el árbol real.
2. Una Skill con un requisito insatisfecho produce la **pregunta** que lo desbloquea, sin gastar un token ni tocar un fichero.
3. Ninguna afirmación de una Skill puede construirse sin naturaleza epistémica: intentarlo levanta un error.
4. Un efecto no autorizado **no se aplica**, y hay un test que lo demuestra sobre un fichero real comparando su sha256 antes y después.
5. Matar la ejecución a mitad y relanzarla no repite ningún paso ya sellado, y el resultado final es idéntico.
6. Un paso que falla deja las ramas independientes ejecutadas y aparece en el acta como no hecho, con motivo.
7. El acta enumera, para cada dato, la Skill, la capacidad, la versión y la entrada que lo produjeron; y su lista de «no comprobado» se deriva de los manifiestos.
8. Una verificación que falla impide que el resultado se marque como verificado.
9. Ninguna Skill ni capacidad importa transporte (Flask, FastAPI, HTTP): test de CI.
10. El agente no puede escribir un fichero de Skill: la propuesta es un documento, no una instalación.

## 9. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | **Sobreingeniería.** Un sistema de Skills para tres Skills es un framework sin usuarios | Se implementa con Skills reales desde el primer día, y el criterio de cierre es que una Skill nueva sea un fichero — no un diagrama |
| R2 | **Compite con el vertical.** El plan de migración v2 subordina todo al cuadro de superficies | Real, y hay que decirlo: esto **adelanta** trabajo de V1-4/V1-10 a V1-12. Se justifica porque el vertical necesitaba ese trabajo igualmente, no porque sea más bonito |
| R3 | **El corpus sigue vacío.** Una Skill normativa sin corpus entrega huecos | La honestidad del hueco es una funcionalidad: `materias_sin_cobertura` viaja en cada respuesta. Pero no sustituye al curador |
| R4 | **La verificación se vuelve teatro.** Comprobaciones que siempre pasan | Toda verificación tiene que poder fallar, y un test la hace fallar a propósito |
| R5 | **El agente propone Skills sin parar.** Ruido en vez de señal | La propuesta se registra, se deduplica por objetivo y no se muestra hasta que se repite |

## 10. Impacto sobre módulos existentes

- **Se amplía:** `agente/` (creado hoy). Nada de lo existente se rompe: `capacidad.py`, `registro.py` y `nucleo.py` conservan su contrato.
- **Se reutiliza sin tocar:** `normativa/` (motor y corpus), `modelo/` (grafo, `Atributo`, invariantes, sellado), `analyzer/parser.py` y `analyzer/superficie_util.py`, `ia/cliente.py` y `ia/uso.py`.
- **No se toca:** `app.py`, `static/index.html`, `analyzer/evaluator.py` ni el camino de `/api/analizar`. El camino viejo sigue con `List[Room]`; el nuevo vive aparte. Es el estrangulador del plan v2.
- **Consumidores indirectos a vigilar:** `tests/test_scripts_legacy.py` ejecuta 72 scripts que importan `analyzer/`; cualquier cambio ahí los afecta, y por eso no se hace ninguno.

## 11. Plan de implementación dividido en pequeñas tareas

| # | Tarea | Depende de |
|---|---|---|
| S-1 | `agente/afirmacion.py`: naturaleza epistémica (hecho, cálculo, inferencia, propuesta) sobre el vocabulario de `modelo/atributo.py`, sin duplicarlo | — |
| S-2 | `agente/memoria.py`: memoria de proyecto append-only con procedencia, conflictos declarados y consulta por requisito | S-1 |
| S-3 | `agente/skill.py`: el `dataclass Skill` con requisitos, capacidades, produce, verificaciones y efectos | S-1 |
| S-4 | `agente/registro.py`: descubrimiento de Skills junto al de capacidades, con `id` único y comprobación de que las capacidades declaradas existen | S-3 |
| S-5 | `agente/verificacion.py`: verificaciones deterministas declarables, con resultado tipado | S-1 |
| S-6 | `agente/efectos.py`: catálogo de efectos y portero de autorización | S-3 |
| S-7 | `agente/ejecucion.py`: ejecutor de Skills con checkpoints, reanudación y continuación ante fallo de una rama | S-4, S-5, S-6 |
| S-8 | `agente/acta.py`: acta de procedencia derivada, sellada | S-7 |
| S-9 | Tres Skills reales sobre lo que ya existe | S-7 |
| S-10 | `agente/carencias.py`: detección y propuesta de Skills que faltan | S-4 |
| S-11 | Integración en `nucleo.py`: las Skills se ofrecen al modelo junto a las capacidades | S-7 |
| S-12 | Tests de todo lo anterior, incluidos los que hacen fallar cada guarda a propósito | todas |

## 12. Plan de pruebas

- **Unidad y contrato** por módulo, con el patrón que el repositorio ya usa: probar que la guarda **muerde**, retirándola a mano y viendo el rojo.
- **Bucle completo** con cliente guionizado, sin red y sin gasto, como en `tests/test_agente_nucleo.py`.
- **Herramientas reales** contra el corpus real: `tests/test_agente_herramientas.py` ya lo hace y se amplía.
- **Efectos:** sha256 del fichero del cliente antes y después, el patrón de `tests/test_cuadro_superficies_export.py`, elevado a política.
- **Reanudación:** interrumpir a mitad, relanzar, comparar el resultado con el de una ejecución no interrumpida.
- **Suite completa** en verde con el comando de CI antes de dar nada por cerrado.

## 13. Métricas para medir el éxito

1. **Coste de una capacidad nueva**: ficheros tocados para añadir una Skill. Objetivo: 1. Hoy, para una funcionalidad: entre 4 y 6.
2. **Proporción de entregables con acta completa**: 100 %, o el acta no es una garantía.
3. **Preguntas concretas frente a fallos genéricos**: de las ejecuciones que no terminan, cuántas acaban en una pregunta accionable. Es la métrica que distingue un copiloto de un formulario roto.
4. **Cifras sin respaldo** detectadas por ejecución. Tendencia a cero; cualquier valor por encima es una fuga.
5. **Reanudaciones correctas** tras interrupción: 100 %, medido con un test.

Lo que **no** se mide: número de Skills. Es la métrica que empuja a fabricar Skills que nadie usa.

## 14. Posibles motivos para NO implementar la idea

Cuatro, y el tercero es serio.

1. **Compite con el vertical, y el plan v2 dice que todo se subordina a él.** Es cierto. La defensa es que V1-4, V1-10, V1-11 y V1-12 son exactamente esto y el vertical no puede existir sin ellas; lo que se adelanta es el *orden*, no el trabajo. Lo que sí queda expuesto es que Postgres, almacenamiento y la pantalla siguen sin hacerse, y sin eso no hay estudio ajeno usándolo.
2. **Sin corpus, la mitad de las Skills profesionales no se pueden escribir.** Una memoria justificativa cita normativa; con una regla transcrita, cita una. El sistema de Skills no arregla eso y no debe disimularlo. **Si hubiera que elegir entre esto y contratar al curador, se contrata al curador.**
3. **El riesgo real no es técnico: es que un arquitecto no delegue.** Todo esto asume que alguien pedirá «prepárame la memoria justificativa» y aceptará el resultado. Un profesional que firma no delega en algo que no entiende. Por eso el acta y la marca de borrador no son accesorios del plan: son la condición para que el plan tenga sentido. Si al probarlo con arquitectos reales resulta que quieren herramientas y no un colaborador, **esta arquitectura sobra** y lo correcto sería un catálogo de herramientas excelentes sin agente encima.
4. **Alternativa mejor, y hay que decirla:** empezar por **una sola** Skill escrita a mano, sin sistema, y ver si alguien la usa. Es más barato y responde antes a la pregunta del punto 3. No se ha hecho así porque las piezas transversales —memoria, verificación, efectos, acta, reanudación— hacen falta igual para una Skill que para veinte, y escribirlas «a mano dentro de la primera» es como acaban las cosas incrustadas para siempre. Pero es una alternativa legítima y quien apruebe este PRD debería saber que existe.
