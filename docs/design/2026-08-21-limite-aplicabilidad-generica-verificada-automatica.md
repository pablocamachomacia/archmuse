# Límite real: `aplicabilidad` genérica choca al hacer VERIFICADA_AUTOMATICA descubrible

**Fecha:** 2026-08-21 · **Encontrado en:** Prompt 2, tarea 8 (ejecución real) · **Estado:** sin resolver, anotado para no perderlo

---

## El hallazgo

Al promover las 3 primeras reglas reales a `VERIFICADA_AUTOMATICA`
(`scripts/verificar_doble_ruta.py`, `docs/prd/2026-08-21-verificacion-doble-
del-corpus.md`) y quitarles el prefijo `_` para que
`normativa/loader.py::descubrir()` las viera —el punto entero de
"promoción"—, la carga del corpus **entero** se rompió:

```
[14] es.rd_173_2010.seguridad_utilizacion.4_1_alumbrado_normal_en_zonas_de_circulacion
     y es.rd_173_2010.seguridad_utilizacion.1_2_discontinuidades_en_el_pavimento
     compiten por la misma materia, ámbito y perfil: el resolver tendría que
     desempatar en silencio
```

`normativa/validacion.py::validar_sin_contradiccion` (validación 14) agrupa
las reglas por `(materia, ámbito, usos, tipologías, tipos_de_intervención,
patrón)`. Las tres reglas promovidas —resalto de junta (1.2), factor de
uniformidad de iluminación (4.1), aforo de graderíos (5.1)— son exigencias
**completamente distintas**, pero ninguna declara `aplicabilidad.usos` ni
`tipologias`: `scripts/generar_borrador_corpus.py::_construir_documento`
(reutilizada sin cambios por la ruta de verificación doble) siempre emite
`aplicabilidad: {ambito: es}` a secas. Con esa clave tan genérica, las tres
son indistinguibles para la validación 14, que hace exactamente lo que tiene
que hacer: negarse a cargar un corpus donde el resolver tendría que
desempatar sin que nadie lo haya decidido.

**Consecuencia inmediata:** `loader.cargar()` es fail-closed a nivel de
CORPUS COMPLETO cuando `validar_corpus` (las validaciones globales)
encuentra un fallo — no solo rechaza los ficheros en conflicto, vacía
`resultado.ficheros` entero. Con las 3 reglas descubribles, hasta
`seguridad_incendio.yaml` —la única regla real que llevaba semanas
funcionando— dejaba de cargar. Se revirtió antes de comprometerlo: las 3
`VERIFICADA_AUTOMATICA` siguen en fichero `_verificada_db_sua_*.yaml`
(prefijo `_`, invisibles al loader, igual que `BORRADOR`).

## Por qué esto es una tarea distinta de "afirmable"

`normativa/resolucion.py::_paso1_candidatas` ya sabe que `VERIFICADA_AUTOMATICA`
es afirmable (docs/prd/2026-08-21-verificacion-doble-del-corpus.md, tarea 3).
Eso resuelve **qué hace el motor con una regla que sí llega**. No resuelve
**si esa regla puede convivir en el mismo directorio que sus hermanas sin
que el corpus entero se caiga al cargar** — eso es la validación 14, y es
correcta al bloquearlo: tres exigencias que de verdad son distintas no
deberían competir por indistinguibles.

## Qué hace falta para cerrarlo (no hecho aquí, a propósito)

`_construir_documento` necesitaría derivar `aplicabilidad.usos`/`tipologias`
reales por regla, no `{ambito: es}` genérico — y eso exige criterio sobre
qué usos/tipologías del catálogo (`normativa/esquema/usos.yaml`) le
corresponden a cada exigencia, leyendo `condicion_aplicacion`/
`explicacion_tecnica` de la candidata de origen. Es trabajo real, no una
línea: cada una de las 20 candidatas de DB-SUA tiene su propia condición de
aplicación en prosa libre, y traducirla al catálogo cerrado sin inventar
alcance es exactamente el tipo de decisión que este proyecto no automatiza
a la ligera (ver `docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md`
§14 sobre no cruzar fronteras de interpretación sin criterio).

**No es bloqueante para el Prompt 2**: su criterio de aceptación es "dos
rutas independientes coinciden en valor y unidad", y eso ya está verificado
y registrado (`estado: VERIFICADA_AUTOMATICA`, con SHA-256 del PDF). Es
bloqueante para que esas reglas entren en producción real y las use el
Prompt 3 (`revision_normativa`) — anotado aquí para que esa sesión no
descubra la misma sorpresa sin aviso previo.
