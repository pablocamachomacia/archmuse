# -*- coding: utf-8 -*-
"""Herramientas de curación del corpus normativo: papel → ledger → YAML.

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md`.

Paquete propio, FUERA de `scripts/`, por dos motivos: `scripts/` estaba
congelado la semana en que esto se construyó, y el flujo de validación sobre
papel (hoja de revisión → acta escaneada → volcado firmado) es una herramienta
permanente del proceso de curación, no un script suelto.

Tres módulos, tres momentos:

- `comprobar_borradores` — antes de imprimir: valida los `_paquete_*.yaml`
  contra las validaciones por fichero y muestra la huella de cada regla.
- `hoja_de_revision` — genera el documento que el validador revisa en papel:
  una página de decisiones por paquete (la única que se firma) más el anexo de
  literales.
- `volcar_acta` — después de la sesión: `transcribir` pasa el acta al ledger
  append-only (`extraccion/estado/curacion/actas_papel.jsonl`) y `firmar`
  escribe las reglas `FIRMADA` en `normativa/es/estatal/` — la única acción de
  este paquete que toca el corpus, inmutable y reanudable, mismo contrato que
  `scripts/curar_corpus.py firmar`.
"""
