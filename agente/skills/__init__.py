# -*- coding: utf-8 -*-
"""Las Skills de ArchMuse: procedimientos profesionales declarados.

Añadir una Skill es dejar un fichero aquí que exponga `SKILLS`. No hay que
tocar este `__init__.py` ni ningún registro central — si alguna vez hiciera
falta, el descubrimiento habría dejado de funcionar y eso sería el fallo.

**Las mismas dos reglas de dependencia que `agente/herramientas/`:** nada de
aquí importa transporte (Flask, FastAPI, HTTP), y nada de aquí importa
`agente/nucleo.py`. Una Skill no sabe que existe un agente; se puede invocar
desde la web, desde un `python -c`, desde un servidor MCP o desde un
complemento de Revit sin cambiar una línea. Lo vigila un test, no la costumbre.

**Lo que las Skills de hoy tienen en común, y es deliberado:** ninguna
emite criterio profesional. Calculan, citan la fuente oficial que les devolvió
una capacidad, y declaran lo que no saben. Las que sí emitirán criterio —memoria
justificativa, revisión de proyecto, detalles constructivos— están bloqueadas
hasta que se decida quién valida su procedimiento (D-7 en
`docs/design/decisiones-pendientes.md`). Equivocarse ahí no es un bug: es mala
praxis con buena presentación.
"""
