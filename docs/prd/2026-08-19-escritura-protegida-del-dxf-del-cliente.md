# PRD — Escritura protegida del DXF del cliente (tarea `TL-2`)

**Estado:** APROBADO · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-08-19

> **Condiciones de la aprobación (textuales):** original **siempre intacto y verificado por SHA-256**; efecto **explícitamente autorizado**; **`N/D` nunca convertido en número**. Las tres son criterios de aceptación y ninguna admite excepción por configuración.

**Tarea del backlog:** `TL-2` de `docs/AGENTE_BACKLOG.md`. Bloquea `SK-1`, `DOC-2`, `DOC-3`, `SEG-1` y, con ellas, el objetivo de producto `OP-1` entero.

---

## 1. Problema que resuelve

El primer entregable vendible de ArchMuse (`OP-1`) no es una pantalla: es **el DXF del arquitecto, devuelto con su cuadro de superficies relleno**. Ese es el momento en el que el producto deja de ser una demostración y pasa a tocar el fichero de trabajo de un cliente.

Ese momento es también el más caro de equivocarse de todo el producto. Un análisis erróneo se descarta; un plano corrompido, sobrescrito o rellenado con una cifra inventada es un daño en el material de trabajo del arquitecto, y en el peor caso viaja a una obra. `DESTROY_ARCHMUSE.md` nombra la pérdida de confianza como el mecanismo de abandono nº 1, y no hay forma más rápida de perderla que tocar un fichero que no era tuyo.

**Lo que hoy existe y lo que falta.** `analyzer/cuadro_superficies_export.py::exportar_cuadro_relleno` ya escribe una copia sin tocar el original, y `tests/test_cuadro_superficies_export.py` ya comprueba el sha256 del origen. Es decir: **la técnica está resuelta y probada**. Lo que no existe es que eso sea una **política del sistema** en vez de una buena costumbre de un módulo: hoy nada impide que la próxima capacidad que escriba un fichero lo haga sin esas garantías, porque no hay ningún sitio donde estén escritas de forma ejecutable.

Este PRD no inventa una técnica. Eleva una que ya funciona a contrato del agente.

## 2. Usuario afectado

El arquitecto que sube su plano por primera vez, que es el único usuario que importa en esta fase. No conoce ArchMuse, no se fía todavía, y su decisión de volver o no se juega en si el fichero que recupera es reconociblemente el suyo.

En segundo plano, el propio ArchMuse como autor de capacidades futuras: la política existe para que la escritura número siete la haga alguien que no leyó este documento y salga igual de bien.

## 3. Objetivo de negocio

Tres cosas, en orden de importancia:

1. **Permitir que exista un entregable.** Sin escritura no hay `OP-1`, y sin `OP-1` no hay nada que vender: el resto del backlog produce pantallas.
2. **Hacer creíble la frase de venta.** «Tu plano no se toca» verificada byte a byte es un argumento comercial comprobable, no una promesa. Es de las pocas cosas que un competidor puramente LLM no puede decir sin mentir.
3. **Proteger el flanco jurídico.** Junto con `DOC-3` (marca de borrador) y `SEG-1` (aprobación explícita), delimita que ArchMuse **asesora y no firma**.

## 4. Objetivo técnico

Una vez implementado, esto debe ser cierto del sistema, observable desde fuera:

- Existe una capacidad de naturaleza `io` que produce un DXF nuevo con el cuadro relleno.
- **El fichero de origen conserva su sha256** después de cualquier ejecución, con éxito o con fallo.
- La copia se **vuelve a abrir y validar** antes de darse por buena; una copia corrupta es un fallo, no una entrega.
- **Ninguna celda se rellena con una cifra que ArchMuse no haya calculado o que el arquitecto no haya declarado.** Una celda `NO_DISPONIBLE` o `BLOQUEADA` se deja sin escribir, y se dice cuál y por qué.
- Ninguna celda preexistente se sobrescribe, coincida o no con lo calculado.
- El destino **nunca** puede ser el origen, ni por igualdad de ruta, ni por enlace simbólico, ni por diferencia de mayúsculas en Windows.
- No se escribe **ningún otro fichero** además del destino declarado.
- El efecto `escribe_fichero` está declarado en el manifiesto, y el portero de efectos (`agente/efectos.py`) rechaza la ejecución sin autorización explícita.
- La política es **de sistema, no del módulo**: un test recorre el registro y falla si una capacidad `io` de escritura no la respeta.

## 5. Casos de uso

**CU-1 · El caso bueno.** El arquitecto sube `v2s.dxf`, autoriza la escritura, y descarga `v2s_ArchMuse_relleno.dxf` con 14 de 18 celdas rellenas y 4 marcadas como pendientes, con su motivo. Su `v2s.dxf` sigue igual.

**CU-2 · Con respuestas del arquitecto.** El arquitecto contesta las preguntas pendientes (qué pieza es cada espacio exterior, la superficie construida, el número de unidades). Se genera una copia nueva con esas celdas rellenas y **marcadas como declaradas por él**, no como calculadas por ArchMuse. La distinción se conserva en el acta.

**CU-3 · Segunda pasada.** Vuelve al día siguiente con el mismo plano. La copia anterior no se sobrescribe en silencio: cada ejecución produce su propio destino, y el acta dice cuál salió de qué versión del grafo.

**CU-4 · Sin autorización.** El plan incluye la escritura, pero nadie la ha autorizado. La ejecución se detiene **antes de abrir el fichero para escribir**, y se muestra qué iba a pasar: qué fichero, qué celdas, qué coste.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Destino == origen (misma ruta, distinta capitalización, o enlace) | Se rechaza antes de abrir nada. `ValueError` con el motivo, nunca una escritura «con cuidado» |
| El DXF no trae `ACAD_TABLE` de cuadro | `ok: false` con la pregunta. No se inventa una tabla ni se escriben MTEXT sueltos |
| El DXF trae más de una vivienda | `ok: false` con el motivo. Elegir «la primera» sería un repliegue silencioso |
| El cuadro trae una celda que ya tenía texto | Se conserva **literal**, no se reformatea ni se recalcula. Se anota como omitida |
| El cuadro no trae celda destino para un campo calculado | Se omite y se dice. No se inventa dónde escribir |
| La copia sale corrupta | El fallo se propaga. Un fichero ilegible no se entrega «por si acaso sirve» |
| El disco se llena a mitad | El destino queda inválido, pero el **origen sigue intacto** — que es la única garantía que no puede fallar |
| El fichero de origen está abierto en AutoCAD | La lectura funciona; el original no se toca, así que el bloqueo de escritura de Windows no llega a ejercerse |
| Escala indeterminada | Se pregunta antes de calcular nada, así que no se llega a escribir (ya cubierto por `TL-1`) |

## 7. Flujo del usuario

1. Sube el DXF y pide el cuadro de superficies.
2. ArchMuse calcula el borrador (`plano.cuadro_de_superficies`, ya existente) y le enseña **qué va a escribir y qué no**, celda a celda, con el motivo de cada hueco.
3. Si hay preguntas pendientes, las contesta —o decide dejarlas en blanco.
4. ArchMuse pide autorización explícita, diciendo: qué fichero se va a crear, que el original no se toca, y qué va a costar.
5. El arquitecto autoriza.
6. Descarga la copia rellena, marcada como borrador para revisión colegiada (`DOC-3`), con su acta de procedencia (`DOC-1`).

## 8. Criterios de aceptación

1. `plano.escribir_cuadro(ruta_origen, ruta_destino, respuestas=None)` existe en el registro con naturaleza `io` y efecto `escribe_fichero` declarado.
2. Sobre el `v2s.dxf` real: la copia sale con las celdas calculadas y el **origen conserva su sha256**, comprobado en test.
3. Un intento con `ruta_destino == ruta_origen` —incluyendo variantes de capitalización y enlaces— falla **sin abrir el origen en escritura**.
4. Ninguna celda `NO_DISPONIBLE` o `BLOQUEADA` aparece con un número en la copia; el resultado lista cuáles quedaron sin escribir y por qué.
5. Una celda preexistente sale byte a byte igual que entró.
6. Ejecutar sin autorización devuelve el rechazo del portero de efectos y **no crea ningún fichero** (comprobado listando el directorio antes y después).
7. La copia se reabre y valida antes de devolverse; un destino corrupto es un fallo explícito.
8. Un test de política recorre el registro y falla si una capacidad `io` que escribe ficheros no declara su efecto o no pasa por el mismo camino de protección.
9. La suite entera sigue verde, incluidos los tests existentes de `cuadro_superficies_export`.

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| La política se queda en «una función bien escrita» y la segunda capacidad de escritura no la respeta | **Alta** — es el modo de fallo por defecto | Alto | El criterio 8: test de política sobre el registro, no sobre el módulo |
| Se generaliza la escritura antes de tiempo (a IFC, a PDF, a modificar geometría) | Media | Alto | Fuera de alcance explícito, §14. `OP-8` no empieza hasta que esto lleve meses en uso |
| La autorización se convierte en un diálogo que todo el mundo acepta sin leer | Alta | Medio | Enseñar **el efecto concreto** (este fichero, estas celdas, este coste), no un «¿continuar?» genérico |
| Un `ezdxf` que evolucione cambie el formato de la copia | Baja | Medio | La versión se fija en `requirements.txt`; la reapertura de validación detecta la rotura en el momento |
| Windows: rutas largas, unidades de red, permisos | Media | Bajo | El origen nunca se abre en escritura; el peor caso es que el destino falle, no que el original se dañe |

## 10. Impacto sobre módulos existentes

- **`analyzer/cuadro_superficies_export.py`:** no se reescribe. Se envuelve. Su lógica ya está probada y tocarla sólo puede empeorarla.
- **`agente/herramientas/plano.py`:** una capacidad más, la primera `io` del registro. El registro pasa de 7 a 8 — sigue dentro del techo de C4 (8-12).
- **`agente/efectos.py`:** ya existe el portero. Esta tarea es su primer usuario real; hasta ahora sólo lo probaban los tests.
- **`app.py`:** **no se toca.** Los endpoints actuales (`/api/exportar-cuadro-superficies`) siguen funcionando por su camino, sin enterarse de que existe una capacidad. El camino viejo se congela, no se migra.
- **`tests/`:** un fichero nuevo y ninguna modificación de los existentes. Si un test existente hay que cambiarlo, es señal de que se ha cambiado un comportamiento y hay que decirlo.

## 11. Plan de implementación (tareas de ~1 jornada o menos)

| # | Tarea | Salida verificable |
|---|---|---|
| 1 | `_destino_seguro(origen, destino)`: normaliza, resuelve enlaces, compara sin distinguir mayúsculas en Windows, y rechaza con motivo | Test con las cuatro variantes de colisión |
| 2 | Capacidad `plano.escribir_cuadro` envolviendo `exportar_cuadro_relleno`, con `naturaleza="io"` y `efectos=("escribe_fichero",)` | Aparece en el registro; `--comprobar` del CLI sigue verde |
| 3 | Resultado estructurado: celdas escritas, celdas omitidas con motivo, sha256 del origen antes y después, sha256 del destino | Golden del resultado (con las rutas como volátiles) |
| 4 | Test de política: toda capacidad `io` que escribe declara su efecto y conserva el sha256 de sus entradas | Rojo si alguien añade una escritura sin protección |
| 5 | Comprobar que no se escribe ningún otro fichero: listado del directorio antes y después | Test |
| 6 | Documentar en `docs/design/2026-08-18-arquitectura-agentica.md` que la escritura tiene su patrón, con enlace a este PRD | El documento lo refleja |

Estimación: **2 jornadas**, que es lo que dice el backlog.

## 12. Plan de pruebas

- **Unitarias, sin fichero real:** el DXF sintético de `tests/test_agente_goldens.py::construir_dxf` cubre el rechazo por destino inseguro, la ausencia de cuadro y el contrato de resultado.
- **Con el DXF real (`ARCHMUSE_DXF_V2S`):** el caso bueno completo, las 18 celdas, el sha256 del origen y la reapertura del destino. Se salta con motivo si la variable no está, mismo criterio que el resto de la suite.
- **De política:** recorrido del registro (criterio 8).
- **De regresión:** `tests/test_cuadro_superficies_export.py` y `tests/test_exportar_cuadro_superficies_endpoint.py` tienen que pasar **sin tocarlos**. Son la prueba de que el camino viejo no se ha movido.
- **Manual, una vez:** abrir la copia en AutoCAD o en un visor DXF y comprobar que la tabla se ve bien. Ningún test automático dice eso.

## 13. Métricas de éxito

1. **Cero incidencias de fichero dañado.** No es una métrica que suba: es una que tiene que quedarse en cero, y si deja de estarlo, se para todo.
2. **Proporción de celdas rellenas sobre el total** en planos reales. Si es baja de forma sistemática, el problema no es la escritura sino el cálculo, y eso cambia la prioridad del backlog.
3. **Cuántos arquitectos vuelven a subir un segundo plano.** Es la única señal real de que el entregable sirvió.
4. **Cuántas veces se rechaza la autorización.** Si es alta, el diálogo asusta o no se entiende; si es cero, es que nadie lo lee.

## 14. Motivos para NO implementar esto

Cuatro, y el tercero es serio:

1. **Ya funciona por la web.** `/api/exportar-cuadro-superficies` hace esto hoy. Se podría vender `OP-1` sin capacidad agéntica ninguna. La respuesta: sin capacidad no hay acta, no hay plan, no hay reproducibilidad y no hay plugin de Revit — o sea, se vendería el entregable renunciando al foso. Pero conviene tener claro que **el valor inmediato de esta tarea es cero para el usuario**: lo que aporta es que el mismo entregable pase a ser componible.
2. **Escribir en el fichero de un cliente es el riesgo más alto del producto** y se está asumiendo antes de tener autenticación, base de datos o despliegue. Si algo sale mal, sale mal en el portátil de Pablo con un cliente real dentro.
3. **El corpus normativo sigue vacío,** y todo lo que no sea `NOR-1`/`NOR-2` compite por el mismo tiempo. Un producto que rellena cuadros de superficies impecablemente y no puede verificar una sola norma es una utilidad, no ArchMuse. Este PRD se sostiene sólo porque `NOR-1` es trabajo de contratación que avanza en paralelo y no consume jornadas de programación; **si eso deja de ser cierto, esta tarea se aplaza**.
4. **Alternativa más barata que se ha descartado:** entregar el cuadro sólo en PDF y no tocar el DXF. Evitaría todo el riesgo de §9. Se descarta porque el DXF relleno es exactamente lo que ahorra la tarde de trabajo; un PDF obliga a teclear los números a mano, y entonces el producto no ahorra nada — sólo comprueba.

---

**Decisión pendiente de Pablo.** Este PRD no se implementa hasta que esté aprobado explícitamente. Si la respuesta es «adelante», la primera tarea es la 1 de §11, no la 2: el rechazo del destino inseguro antes que la escritura.
