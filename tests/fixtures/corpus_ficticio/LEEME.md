# Corpus FICTICIO — no es normativa

Todo lo que hay bajo este directorio es **inventado**. Los boletines, los
identificadores oficiales y las cifras no corresponden a ninguna norma real y
**no deben citarse jamás**, ni copiarse al corpus de producción.

Existe por un motivo concreto: el motor de resolución de la Fase 1 se puede
—y se debe— probar sin normativa real. Transcribir una sola cifra autonómica
exige un arquitecto colegiado que la valide contra boletín (tarea 18 del PRD
`2026-08-06-motor-de-normativa-territorial`), y ese cuello de botella no tiene
por qué bloquear la verificación del algoritmo.

La separación es estricta y deliberada:

- `normativa/` — corpus real. Hoy **vacío**. Solo entra ahí lo verificado.
- `tests/fixtures/corpus_ficticio/` — este. Solo lo cargan los tests, pasando
  `raiz_corpus=` explícitamente. Ninguna ruta de producción lo alcanza.

Si algún día una regla de aquí aparece en un informe, el fallo no será de este
directorio: será de quien haya pasado `raiz_corpus` en producción.

## Qué ejercita

| Fichero | Para qué está |
|---|---|
| `es/estatal/seguridad_incendio.yaml` | Umbral con tabla de parámetros; regla condicionada a un hecho del proyecto; regla derogada antes de la fecha de devengo |
| `es/estatal/accesibilidad.yaml` | Base de una materia en modo `suelo`, para que la autonómica la endurezca |
| `es/estatal/otras_exigencias.yaml` | Relleno de las materias estatales restantes, para que la cobertura declarada cuadre con el disco (validación 17) |
| `es/13-madrid/autonomico/habitabilidad.yaml` | Materia autonómica exclusiva; regla excluida por uso; **dos reglas que se solapan sin ser idénticas → conflicto no resuelto** |
| `es/13-madrid/autonomico/accesibilidad.yaml` | Endurecimiento declarado sobre el suelo estatal |
| `es/13-madrid/municipios/28115-.../urbanismo.yaml` | Materia municipal exclusiva |
| `es/13-madrid/municipios/28115-.../patrimonio.yaml` | Ámbito sectorial no declarado, y exención condicionada |
