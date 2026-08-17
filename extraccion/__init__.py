"""Extracción inteligente del CTE — Fase 2 del pipeline de ingesta.

Ver `docs/design/2026-08-06-extraccion-cte.md`.

Dos pasos, dos módulos: `segmentador.py` (determinista, sin IA) parte un
`ingesta.modelo.DocumentoOficial` en `Segmento`s; `interprete.py` (usa la API
de Anthropic) convierte cada segmento en una `ReglaCandidata`, verificada por
`verificacion.py` y con confianza calculada por `confianza.py` — ninguna de
las dos últimas llama a ningún modelo, y por eso se prueban sin gastar un
token.

**Frontera, igual que `ingesta/`**: este paquete no escribe en `normativa/es/`
ni lo importa como destino. Sí importa, de forma explícita y acotada, los
catálogos cerrados de `normativa/` (`normativa.modelo`, `normativa.catalogos`)
para no reinventar el vocabulario de tipos/patrones/materias — la misma
clase de excepción que ya tiene `analyzer/cte_zonas.py`. `test_extraccion_fronteras.py`
vigila que no se amplíe sin querer.
"""
