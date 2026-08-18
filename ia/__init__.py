"""Infraestructura compartida para hablar con modelos de lenguaje.

**Por qué es un paquete de primer nivel y no vive en `analyzer/`.** Seis
módulos del repositorio construyen un cliente de Anthropic, y no todos pueden
importar `analyzer/`: `extraccion/interprete.py` lo tiene **prohibido** por la
frontera que vigila `tests/test_extraccion_fronteras.py`. Una fachada que solo
la mitad del repositorio puede usar no es una fachada.

Aquí no va lógica de dominio: ni prompts, ni esquemas de herramienta, ni
interpretación de respuestas. Solo la construcción del cliente y sus límites.
Cada módulo sigue siendo dueño de qué le pide al modelo y de qué hace con lo
que devuelve.
"""
