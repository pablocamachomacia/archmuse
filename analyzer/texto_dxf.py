# -*- coding: utf-8 -*-
"""Texto de un DXF, convertido en texto legible. Un solo sitio.

Este módulo existe por un fallo concreto y medido (2026-09-10, `v1plantas.dxf`):
AutoCAD guarda las tildes y las eñes de un TEXT o un MTEXT como una secuencia de
escape —`ba\\U+00F1o`, `sal\\U+00F3n`— y **`plain_text()` de ezdxf 1.4.4 no la
decodifica**. Nadie en `analyzer/` lo hacía tampoco, así que el rótulo `Ba\\U+00F1o`
no casaba con el patrón `\\bBANO\\b` y **el baño de esa vivienda no se medía**:
la pieza quedaba sin clasificar y bloqueaba la publicación de las superficies de
la vivienda entera.

**Por qué un módulo propio y no una función dentro de `parser.py`.** Hace falta
en dos sitios que están separados a propósito: `parser._texto_de` (el rótulo que
se lee del plano) y `cuadro_superficies._normalizar` (la etiqueta que se lee del
cuadro del arquitecto). `cuadro_superficies.py` **no importa `parser.py`**, y esa
decisión está escrita y razonada en su docstring. Un módulo sin dependencias que
los dos pueden importar respeta esa separación y deja una sola implementación de
la conversión, que es lo que impide que dentro de un año una de las dos ramas
sepa decodificar una eñe y la otra no.
"""
from __future__ import annotations

import re
from typing import Optional

#: `\U+XXXX` con exactamente cuatro dígitos hexadecimales, que es como lo
#: escribe AutoCAD. Cualquier otra cosa —`\U+`, `\U+ZZZZ`, una barra invertida
#: suelta de una ruta de Windows— no es un escape y se deja intacta: inventarse
#: una conversión sobre algo que no se reconoce es peor que no tocarlo.
_ESCAPE_UNICODE = re.compile(r"\\U\+([0-9A-Fa-f]{4})")


def decodificar_escapes(texto: Optional[str]) -> str:
    """`"ba\\U+00F1o"` -> `"baño"`. Lo que no sea un escape se deja como está.

    Es **idempotente**: aplicarlo a un texto ya decodificado no lo cambia. Eso
    es lo que permite ponerlo en los dos extremos sin tener que coordinarlos ni
    razonar sobre cuál se ejecuta antes.
    """
    if not texto:
        return ""
    return _ESCAPE_UNICODE.sub(lambda m: chr(int(m.group(1), 16)), texto)
