# Addendum al Prompt 2 — verificación doble

**Fecha:** 2026-08-21 · **De:** Pablo, tras el cierre del Prompt 1.5 (descomposición) · **Estado:** no implementado, para cuando se abra la sesión del Prompt 2

Este fichero recoge instrucciones que Pablo dio para el Prompt 2 (verificación
por transcripción doble, aún sin PRD ni código) mientras el Prompt 1.5
(descomposición) seguía fresco. Se guarda aquí para que la sesión que abra el
Prompt 2 — y su PRD, obligatorio antes de tocar código — parta de esto y no
lo pierda por no compartir contexto de conversación.

## Instrucciones textuales

1. **La doble ruta opera sobre las SUB-CANDIDATAS atómicas** que dejó la
   descomposición del Prompt 1.5 (`_descomponer()`/`_unidades()` en
   `scripts/generar_borrador_corpus.py`), **nunca sobre artículos padre**.
   Ver `docs/prd/2026-08-21-descomposicion-de-candidatas-compuestas.md`.

2. **La segunda ruta de extracción debe usar un motor de texto PDF distinto
   al de la primera**, con tratamiento explícito del guionizado de fin de
   línea. Motivo: el límite conocido del PRD del 1.5 (~7 de las 24
   pendientes caen por `contexto_no_localizable`, guionizado roto del PDF)
   tiene que **aflorar como discrepancia resoluble** entre las dos rutas —
   no quedar invisible porque ambas compartan el mismo defecto de lectura.

3. **Objetivo medible, además del criterio original del Prompt 2:** de las
   24 pendientes actuales (`extraccion/estado/pendientes/codigotecnico__DB-
   SUA__3cfb5bbb135e.pendientes.jsonl`), las que cayeron por
   `posible_cifra_adicional_no_extraida` o `contexto_no_localizable` deben,
   con la segunda ruta:
   - o bien convertir (la segunda ruta ancla lo que la primera no pudo), o
   - o bien llegar a `revisar_pendientes.py` con las dos lecturas lado a
     lado, para que Pablo decida — no seguir cayendo en silencio al mismo
     cajón sin que nadie las vea resueltas ni comparadas.

4. **El guardián `_contar_cifras_de_umbral`** (scripts/generar_borrador_corpus.py)
   se mantiene activo **en ambas rutas**, no solo en la primera — el riesgo
   que detectó (DB-SUA 7.3: convertir la mitad de una disyunción como si
   fuera un umbral incondicional) existe igual de cierto venga la cifra de
   la ruta que venga.

## Qué no cambia

Todo lo demás del Prompt 2 tal como estaba en la secuencia original de
Fable 5 (estados `BORRADOR` → `VERIFICADA_AUTOMATICA`, SHA-256 del PDF
oficial, `scripts/revisar_pendientes.py`, resolución de manifiesto-materia
↔ estado-regla ya acordada en
`docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md` §9) sigue en pie.
