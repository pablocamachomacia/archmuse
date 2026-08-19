# -*- coding: utf-8 -*-
"""Las capacidades que el agente puede ejecutar.

**Regla de dependencia, y es la que hace que esto valga la pena.** Nada de
aquí importa transporte: ni `flask`, ni `fastapi`, ni `request`, ni nada que
sepa de HTTP. Una capacidad se tiene que poder invocar igual desde la API web,
desde un `python -c`, desde un servidor MCP o desde un plugin de Revit sin
reescribir una línea. Es la prueba del plugin del ADR, y la vigila
`tests/test_agente_nucleo.py`, no la buena voluntad.

Tampoco importan nada de `agente/nucleo.py`: la dependencia va del núcleo a las
capacidades y nunca al revés. Una capacidad no sabe que existe un agente.

Añadir una capacidad es dejar un fichero aquí que exponga `CAPACIDADES`. No hay
que tocar este `__init__.py` — si alguna vez hiciera falta, el descubrimiento
habría dejado de funcionar y eso sería el fallo, no el fichero nuevo.
"""
