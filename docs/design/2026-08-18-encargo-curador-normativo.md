# Encargo — Curador de conocimiento normativo

**Fecha:** 2026-08-18 · **Estado:** propuesta, no aprobada · **Cierra:** tarea V0-5 del plan de migración v2
**Para:** un arquitecto colegiado en ejercicio. No hace falta que programe.

---

## 1. El encargo en una frase

Convertir el articulado exigible del Código Técnico de la Edificación, y después la normativa autonómica y municipal, en fichas estructuradas que ArchMuse pueda citar con precisión — siguiendo el procedimiento de `docs/design/2026-08-18-ficha-de-transcripcion-normativa.md`.

## 2. Por qué es el puesto más rentable del proyecto

El motor que aplica normativa está construido, probado y funcionando: 3.777 líneas que resuelven, para un proyecto en un municipio concreto, qué le es exigible y con qué prioridad. **Y prácticamente no tiene contenido.** `normativa/es/` tiene **una** regla —DB-SI 3, tabla 3.1—, transcrita como ejemplo trabajado y **sin firmar por ningún colegiado**. Mientras siga sin firma, ArchMuse no afirma nada sobre seguridad contra incendios: bloquea por falta de cobertura, que es lo correcto y no es un producto.

Ninguna decisión de arquitectura desbloquea eso. No hay atajo de software: transcribir normativa exige criterio profesional y responsabilidad, y por eso lo hace un colegiado y no un modelo de lenguaje. Mientras tanto, ArchMuse aplica 38 reglas con umbrales escritos a mano dentro del código, sin respaldo declarativo ni cita que enseñar.

Dicho de otra forma: **cada semana sin curador es una semana en la que el producto no puede verificar normativa aunque todo lo demás funcione.**

## 3. Alcance

**Entra:**

- Transcripción del articulado exigible según la ficha, en el orden de prioridad de su §1: DB-SI → DB-SUA → DB-HS 3 y DB-HE 1 → autonómico de Madrid → ordenanza municipal, solo donde haya proyectos reales.
- La **lista de dudas** de cada entrega: lo que no se transcribe por ambiguo. Es un entregable, no un residuo.
- Revisión de lo transcrito por otra persona (criterios 5-7 de la ficha), si el encargo incluye a dos.
- Dictamen sobre los casos que el motor no puede resolver solo y marca `UNKNOWN`.

**No entra:**

- Programar, revisar código o diseñar el esquema. Si el esquema estorba a una norma real, se dice y se cambia el esquema.
- Decidir qué construye ArchMuse. El curador dice qué exige la norma, no qué funcionalidad se prioriza.
- Firmar proyectos ni asumir responsabilidad sobre lo que ArchMuse produzca. **ArchMuse asesora; el proyecto lo firma el arquitecto que lo redacta.**

## 4. Entregables y cadencia

| Qué | Formato | Cuándo |
|---|---|---|
| Bloque transcrito | Un `.yaml` por materia y ámbito, según la ficha §2 | Semanal |
| Lista de dudas del bloque | Texto libre, una línea por duda | Con cada bloque |
| Correcciones tras validación | El mismo `.yaml` corregido | En la semana siguiente al rechazo |
| Dictamen de casos abiertos | Texto breve, con la cita que lo sostiene | Bajo demanda |

**Un bloque = una sección coherente de un documento básico**, no reglas sueltas. Es preferible una sección cerrada y revisada por semana que un DB entero sin revisar: el corpus vale por lo que se puede defender, no por lo que ocupa.

**Nadie ha medido todavía cuántas reglas salen de una sesión sobre un DB real.** La primera entrega es también la primera medición, y la cadencia se recalibra con ese dato en vez de con una estimación.

## 5. Criterios de aceptación

Los siete de la ficha §4: cuatro los comprueba la máquina (forma, catálogos, coherencia documento-materia, aristas resolubles) y tres una persona (fidelidad al literal, localización exacta, utilidad del mensaje).

**El criterio que manda sobre todos:** cada número de una ficha aparece en el literal citado. Un número que no esté en el literal se rechaza sin discusión.

**Y una regla de proceso:** ante la duda, no se transcribe. Una regla ausente se ve; una regla mal transcrita, no — y es exactamente el fallo que un arquitecto no perdona dos veces.

## 6. Cómo se mide que el encargo va bien

1. **Cobertura auditada, no cobertura declarada.** Reglas que han pasado las siete comprobaciones, por documento básico, publicadas en `normativa/cobertura/manifiesto.yaml`.
2. **Tasa de rechazo en validación automática**, y si baja con las semanas. Si no baja, la ficha está mal escrita, no el curador.
3. **Dudas abiertas frente a dudas dictaminadas.** Que la primera cifra no crezca indefinidamente.

Lo que **no** se mide: número de reglas por semana en bruto. Es la métrica que empuja a transcribir rápido y mal, y el proyecto ya tiene escrito por qué eso es el peor resultado posible.

## 7. Condiciones prácticas

- **Dedicación:** parcial. El trabajo es acumulativo y no se beneficia de sesiones largas.
- **Herramientas:** un editor de texto y el acceso oficial a boe.es y codigotecnico.org. **La validación automática la ejecuta el propio curador**, con una orden:

  ```
  python scripts/validar_corpus.py
  ```

  Devuelve, en castellano, el fichero, la regla y el motivo de cada problema de forma, y enumera al final los tres criterios que **no** puede comprobar —fidelidad al literal, localización exacta y utilidad del mensaje—, porque esos los decide una persona leyendo el boletín. Hasta el 2026-08-19 esta comprobación sólo se podía ejecutar desde los tests del proyecto, de modo que saber si un YAML estaba bien exigía preguntarle a un programador; eso convertía al equipo técnico en el cuello de botella del único trabajo que no puede tenerlo.
- **Punto de partida:** la ficha de transcripción, ya probada sobre una regla real (DB-SI 3, apartado 3, Tabla 3.1), disponible en `normativa/es/estatal/seguridad_incendio.yaml` como ejemplo trabajado.
- **Primera tarea del encargo, y también su prueba de aceptación:** transcribir **una segunda regla** siguiendo la ficha sin ayuda, y que `python scripts/validar_corpus.py` la acepte. Si no se puede, la ficha está incompleta y se corrige antes de seguir — el defecto sería del procedimiento, no de quien lo sigue.

- **El orden de trabajo de cada regla, que el sistema hace cumplir y no depende de que nadie lo recuerde:** transcribir → declararla en `normativa/cobertura/manifiesto.yaml` como `transcrito_sin_firmar` → conseguir la firma → retirar la etiqueta `pendiente_firma_colegiado` de la regla → sólo entonces promover la materia a `parcial` o `completo`. Adelantar el último paso **falla al cargar** (validación 18): mientras una materia tenga reglas sin firmar, ArchMuse no puede afirmar nada sobre ella aunque el manifiesto lo declare.
