"""Ingesta de normativa oficial — Fase 1: conexión, descarga, versionado.

Ver `docs/design/2026-08-06-ingesta-normativa.md` para el diseño completo.

**Frontera dura, igual que la que protege `normativa/`:** este paquete nunca
escribe dentro de `normativa/es/` ni de ningún directorio que
`normativa/loader.py` descubra. Todo lo que descarga vive en
`ingesta/estado/`, invisible para `normativa_aplicable()` hasta que un humano
lo promueve a mano. `ingesta/` tampoco importa `normativa/` ni `analyzer/`:
no necesita saber nada de resolución territorial ni de evaluación de planos
para descargar un documento y detectar si cambió.
"""
