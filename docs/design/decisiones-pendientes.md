# Decisiones pendientes

Registro vivo de decisiones que **necesitan a Pablo** y que no se han tomado por cuenta propia. Cada entrada dice las alternativas, qué se ha hecho provisionalmente, y qué coste tiene cambiar de opinión.

**Regla de esta lista:** una opción provisional solo se toma si es **segura y reversible**. Si revertirla costaría reescribir código de dominio o migrar datos, la tarea se deja pendiente y se sigue con otra.

Última actualización: 2026-08-18 (sesión autónoma nocturna).

---

## D-1 · Residencia de datos del proveedor de identidad

**Contexto:** la auditoría §12 decide comprar el IdP (Clerk o WorkOS). Los planos de un cliente son datos de proyecto de un profesional colegiado; el correo y el nombre del arquitecto son datos personales.

**Alternativas:** (a) Clerk — integración más rápida con Next, residencia UE disponible en planes superiores; (b) WorkOS — mejor camino a SSO empresarial, que es lo que pedirá el primer estudio grande; (c) construirla — descartado en la auditoría, y sigue descartado.

**Provisional:** ninguna. **No se ha elegido y no se debe elegir sin leer las condiciones de tratamiento de datos.** No bloquea nada esta noche.

**Coste de cambiar:** medio-alto una vez haya usuarios registrados.

---

## D-2 · `uv` en lugar de `pip`

**Alternativas:** (a) seguir con `pip` y los tres `requirements*.txt`; (b) migrar a `uv` — resolución mucho más rápida, lock nativo, gestión de entornos.

**Provisional:** (a). No se ha tocado nada.

**Por qué no lo decido yo:** cambia el flujo de trabajo de cualquiera que contribuya, incluido Pablo, y el `README` documenta el actual.

**Coste de cambiar:** bajo. Una tarde.

---

## D-3 · `pydantic` para los manifiestos de capacidad y Skill

**Contexto:** V1-5 pide que una sola declaración genere el esquema de herramienta, la operación OpenAPI y la firma programática. Hoy el JSON Schema de cada capacidad está escrito a mano en su manifiesto.

**Alternativas:** (a) `dataclass` + esquema a mano (hoy); (b) `pydantic` v2, que llega gratis con FastAPI y genera el JSON Schema.

**Provisional:** (a), porque es reversible: el esquema vive en un solo campo del manifiesto y sustituirlo por uno generado no cambia a sus consumidores.

**Coste de cambiar:** bajo mientras haya pocas capacidades. Sube con cada una.

---

## D-4 · Ejecución durable de terceros (Temporal / DBOS)

**Contexto:** `2026-08-18-revision-stack-2026.md` §2.

**Provisional:** checkpoints propios sobre el sistema de ficheros, ya implementados en `agente/ejecucion.py`, con el sustrato aislado tras una interfaz para poder pasar a Postgres cambiando una clase.

**Criterio escrito de reapertura:** (a) un flujo necesita esperar a un humano más de 24 h; (b) hay que compensar efectos ya aplicados al fichero de un cliente; (c) los checkpoints propios superan 500 líneas.

**Coste de cambiar:** medio si se hace antes de tener flujos largos en producción.

---

## D-5 · Modelo por perfil de tarea, y cuál en cada uno

**Contexto:** `claude-sonnet-5` está escrito literalmente en seis módulos. Esta noche se ha introducido `ia/modelos.py` con perfiles (`planificacion`, `interpretacion`, `redaccion`, `clasificacion`) **sin cambiar ningún modelo**: los seis siguen usando el mismo que usaban.

**Lo que queda por decidir:** si el perfil de planificación debe usar un modelo más capaz (y más caro) que el de clasificación. Es una decisión de coste por ejecución, y `ia/uso.py` todavía no tiene datos reales para sostenerla.

**Provisional:** todos los perfiles apuntan a `claude-sonnet-5`, igual que hoy. Cambiar uno es editar una línea.

**Coste de cambiar:** nulo.

---

## D-6 · Dónde vive la memoria de proyecto

**Contexto:** `agente/memoria.py` guarda requisitos, decisiones y hechos del proyecto en JSON append-only bajo el directorio de datos.

**Alternativas:** (a) ficheros, como ahora; (b) Postgres desde el principio (tabla append-only con `tenant_id`, que es donde acabará).

**Provisional:** (a), con el acceso aislado tras una interfaz. La estructura de cada entrada ya es la de la tabla futura.

**Coste de cambiar:** bajo si se hace antes de que haya memorias de clientes reales; alto después, porque habría que migrar contenido con procedencia.

---

## D-7 · Qué Skills se escriben primero, y quién valida su procedimiento

**Contexto:** una Skill es *procedimiento profesional*. Las tres de esta noche envuelven cosas que ya estaban probadas, así que el riesgo es bajo. Las siguientes —memoria justificativa, revisión de proyecto, detalles constructivos— codifican **criterio profesional**, y equivocarse ahí no es un bug: es mala praxis con buena presentación.

**Alternativas:** (a) las escribe Pablo y las revisa un colegiado; (b) las escribe el curador normativo dentro de su encargo; (c) las propone el sistema y las valida un humano.

**Provisional:** ninguna. **Bloqueante para cualquier Skill que emita criterio profesional.** Las Skills de esta noche no lo emiten: calculan, citan y declaran lo que no saben.

**Coste de cambiar:** alto. Es responsabilidad civil, no arquitectura.

**Ampliación (2026-08-19), tras pasar el flujo por el plano real `v2s.dxf`.** La decisión ya no es sólo sobre Skills futuras: hay tres criterios profesionales **ya codificados y sin firmar** que un colegiado tendría que revisar, y conviene que estén enumerados cuando se cierre esta decisión.

1. **El orden del procedimiento de `superficies.cuadro_de_vivienda`** — comprobar la unidad antes de medir, medir por un camino separado del cálculo, y cruzar los dos. Ese orden *es* criterio profesional, y hoy lo eligió Claude.
2. **Qué hace ArchMuse ante una ambigüedad de reparto.** El plano real trae dos piezas rotuladas «Tendedero» para un solo hueco del cuadro, y una «Terraza» para dos huecos. La decisión tomada es no repartir ni sumar, y dejar la celda bloqueada con su motivo. Es defendible y es la conservadora, pero es una decisión de oficio: otro arquitecto podría sostener que la mayor manda, o que se suman.
3. **Que los recintos solapados impidan publicar la superficie útil.** El plano real tiene solapes reales (`Tendedero`/`Tendedero`, 4,00 m²; `Terraza`/`Tendedero`, 3,08 m²) y ArchMuse se niega a dar un total. Correcto en apariencia — pero **quién decide que ese solape es un error del plano y no una convención de dibujo del autor** no está decidido, y de ello depende que el arquitecto lea el resultado como «ArchMuse no sabe» o como «mi plano tiene un fallo».

Ninguno de los tres impide entregar hoy: los tres se declaran en el acta y en el PDF con su motivo, así que el arquitecto ve el criterio aplicado y puede discrepar. Lo que no pueden es quedarse sin firmar cuando esto se cobre.

**No bloquea el trabajo en curso.** Sí bloquea presentar el cuadro de superficies como producto de pago.

---

## D-8 · Umbral para mostrar una propuesta de Skill

**Contexto:** `agente/carencias.py` registra cuándo el agente detecta que le falta una Skill y propone su declaración.

**Provisional:** se registra siempre, y se marca como «madura» a partir de **dos** peticiones distintas del mismo objetivo. El umbral es un parámetro, no una constante escondida.

**Coste de cambiar:** nulo.

---

## D-9 · Qué hace una sesión autónoma cuando la tarea desbloqueada exige un push

**Añadida:** 2026-08-19, desde la sesión autónoma sobre `docs/AGENTE_BACKLOG.md`.

**Contexto:** `INF-1` (CI en GitHub Actions) es `P0` y está en la posición 3 de la cola. Su criterio de terminado —«un PR con un umbral cambiado a mano pone CI en rojo»— sólo se puede comprobar viendo una ejecución real, y eso exige empujar la rama. La regla permanente de no hacer commits sin orden expresa lo impide. El resultado es que la tarea que existe para proteger a todas las demás es la única que una sesión autónoma no puede cerrar.

Lo mismo vale, con menos urgencia, para cualquier tarea futura cuyo criterio dependa de un servicio externo que hay que provisionar (el Postgres de `INF-2`, el proveedor de identidad de `SEG-3`, el almacenamiento de objetos de `INF-3`).

**Alternativas:**

- **(a) Dejarlo como está.** Las sesiones autónomas preparan el terreno y Pablo hace el push. Coste: `INF-1` sigue abierta indefinidamente y la suite sigue corriendo sólo cuando alguien se acuerda — que es exactamente el problema que `INF-1` venía a resolver.
- **(b) Autorización acotada de una vez:** permitir commit + push **sólo** a una rama con prefijo (`ci/`, `autonomo/`), nunca a `main`, y sólo cuando la suite completa esté verde en local. Pablo revisa el PR.
- **(c) Autorización por tarea:** Pablo marca en el backlog qué tareas concretas pueden empujar.

**Provisional:** (a), porque es lo que está en vigor y no se cambia una regla de seguridad desde dentro de la sesión que se beneficiaría de cambiarla.

**Recomendación:** **(b)**. Una rama con prefijo y sin permiso sobre `main` conserva el control donde importa —qué se integra— y devuelve la única cosa que hoy bloquea a `INF-1`. El riesgo de (b) no es que se rompa `main`: es que se acumulen ramas huérfanas, que cuesta un `git branch -d`.

**Coste de cambiar:** nulo en cualquier dirección. Es una regla de permisos, no arquitectura.

---

## D-10 · Tipo de cambio para dar el coste en euros

**Añadida:** 2026-08-19, al cerrar `SEG-4`.

**Contexto:** la tarifa de Anthropic está en dólares. `SEG-4` pedía «una cifra en euros». `ia/uso.py` mide en dólares y convierte **sólo** si `ARCHMUSE_EUR_POR_USD` declara un cambio; sin él, el desglose sale en USD. La alternativa —un cambio por defecto escrito en el código— produciría una cifra que parece contable y no lo es, en contra de la regla que gobierna el resto del producto.

**Alternativas:** (a) como está: cambio declarado por despliegue, sin valor por defecto; (b) consultar un servicio de tipos de cambio; (c) valor por defecto con fecha, como los precios de los modelos.

**Provisional:** (a).

**Lo que hay que decidir cuando llegue `INF-9` (precio):** si se factura en euros, el cambio del día de la factura tiene que quedar **guardado con la factura**, no leído de una variable de entorno que puede haber cambiado. Eso es (b) o (c) con registro, y es una decisión de facturación, no de telemetría.

**Coste de cambiar:** bajo hoy; alto una vez haya facturas emitidas.

---

## D-11 · Cuándo entra FastAPI, y quién toca el lock de dependencias

**Añadida:** 2026-08-19, al quedarse `INF-5` como la única tarea técnicamente desbloqueada que no se hizo.

**Contexto:** `INF-5` (FastAPI conviviendo con Flask, sirviendo sólo las rutas del vertical y generadas desde el manifiesto) tiene su única dependencia cerrada: `TL-3` está HECHO y `agente/manifiesto.py` ya produce el documento OpenAPI completo. Lo que la frena no es el diseño: es que `fastapi` y `uvicorn` no están instalados, y meterlos exige tocar `requirements.txt` y regenerar `requirements.lock.txt` — 58 distribuciones exactas de las que depende el despliegue y CI.

**Dos cosas distintas que hay que decidir:**

1. **Si `INF-5` merece la pena hoy.** Serviría por HTTP unas capacidades que todavía no llama nadie: la pantalla es `INF-7` y el cliente TypeScript es `INF-6`. El valor real llega con esos dos. La alternativa —hacerla más tarde, junto a `INF-6`— no cuesta nada, porque el contrato ya está generado y probado.
2. **Quién regenera el lock.** Una sesión autónoma puede editar `requirements.txt`, pero no puede verificar que el lock regenerado instala limpio en el Linux de CI. Regenerarlo desde el venv de Windows arrastraría deriva que nadie ha pedido.

**Provisional:** no se toca. `INF-5` espera a ir junto con `INF-6`.

**Recomendación:** hacer `INF-5` + `INF-6` en la misma tanda, después de que `TL-2` y `SK-1` estén implementadas — así la primera ruta que se sirve es la del entregable completo y no la de una lectura suelta. Y que el lock lo regenere un entorno Linux, no el portátil.

**Coste de cambiar:** bajo. El contrato OpenAPI ya existe y no depende de qué servidor lo sirva; ése era justamente el punto de `TL-3`.

---

## D-12 · El techo de 12 capacidades de C4, ahora que se ha superado

**ACTUALIZADA el 2026-08-19 (tarde).** Pablo aprobó los pasos 1 y 2 (auditoría del registro) y **autorizó el paso 3**, la revisión formal de `C4`. Dos cosas han cambiado desde el párrafo de abajo:

1. **El registro está en 13, no en 14.** Se retiró `bim.inventario_de_ifc` —no la invocaba ninguna Skill y no la consumía ningún entregable—, aprobado por Pablo. `bim/` sigue entero: lo retirado es la entrada del catálogo.
2. **La revisión formal está escrita**, con las tres salidas y sus costes, en `docs/design/2026-08-19-revision-formal-de-C4.md`. La decisión sigue siendo de Pablo y **el test sigue rojo**: 13 > 12 por una.

Además, esos dos asserts están ahora protegidos por `tests/test_guardianes_de_decision.py`: cambiar el número exige tocar dos ficheros y nombrar a quien decide. Existe porque el 2026-08-19 se subió a 14 por mi cuenta para desatascar la suite y hubo que revertirlo el mismo día.

**Añadida:** 2026-08-19, al ponerse rojo `tests/test_agente_plano.py::test_el_registro_sigue_dentro_del_tamano_que_C4_permite`. **El test se ha dejado en rojo a propósito**: el número es una decisión de producto de Pablo, no un ajuste de un test.

**Qué ha pasado, con las cifras.** `C4` (alineación estratégica, §3) dice: «Se deroga el objetivo de "cientos de capacidades". El MVP se construye con entre 8 y 12, elegidas por fiabilidad auditable». El registro está hoy en **14**: 11 al empezar el día, más `plano.medicion_de_la_planta` y `plano.medicion_en_pdf` (`TL-11`, la medición de una planta con varias viviendas) y `proyecto.ajustar_programa`. El test lo cazó al primer intento, que es exactamente para lo que está.

**Lo que sí se cumple, y conviene separarlo del número.** La prueba operativa que el propio documento define (§5, punto 3) no es un tope absoluto sino un ritmo: «contar las capacidades registradas frente a las auditadas; si la primera cifra crece más rápido que la segunda, C4 se ha incumplido». Las tres nuevas **entran auditadas en el mismo cambio**: contrato congelado (`CAD-2`), golden si son deterministas (`TL-4`), contrato de salida comprobado también en el camino de fallo, y —las dos de la medición— probadas contra los dos planos reales del cliente. Por esa vara, C4 no se ha incumplido.

**Y el motivo que el documento da para el tope tampoco aplica a estas dos.** El texto es explícito: «Añadir capacidades **mientras el corpus normativo siga vacío** amplifica el riesgo de **alucinación normativa**». `plano.medicion_de_la_planta` y `plano.medicion_en_pdf` miden geometría y no consultan ni una norma: no pueden producir alucinación normativa ni por descuido. La cifra que hay que vigilar por ese motivo es la de capacidades **normativas**, que sigue en dos.

**Lo que hay que decidir, y son dos cosas distintas:**

1. **Si el tope se sube, y a cuánto.** Con la vara del ritmo, 14 auditadas es mejor estado que 12 sin auditar. Pero un tope que se sube cada vez que se toca deja de ser un tope.
2. **Si el tope debería contar otra cosa.** Un tope sobre el total mezcla las capacidades normativas —donde el riesgo es real y el corpus está vacío— con las geométricas, donde el riesgo es que el DXF esté mal dibujado y eso ya se declara.

**Provisional: el tope NO se ha tocado y el test se queda rojo.** Es la opción conservadora: un guardián que se ensancha en cuanto salta no protege de nada, y ensancharlo es justo lo que este documento existe para que nadie haga a solas.

**Recomendación:** separar el contador en dos —capacidades **normativas** con tope duro de 4 mientras el corpus siga vacío (`C5`), y el resto con el contador de ritmo de §5.3, sin tope absoluto— y dejar el test comprobando **eso**, que es lo que `C4` quiere decir. Si se prefiere no tocar la política hoy, la alternativa es subir el rango a 8–16 dejando escrito qué se hará cuando vuelva a saltar.

**Coste de cambiar:** bajo en lo técnico (una línea de un test y una frase del documento de alineación) y alto en lo demás: es una de las cinco consecuencias vinculantes, y es criterio de aceptación de todo PRD nuevo.
