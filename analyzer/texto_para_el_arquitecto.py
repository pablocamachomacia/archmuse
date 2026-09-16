# -*- coding: utf-8 -*-
"""Lo que lee el arquitecto en AutoCAD, sin códigos internos (Pablo, 2026-09-16).

«Los mensajes que ve el arquitecto no deben llevar códigos internos (C-17, C-12,
"propuesto"...). Que expliquen el motivo en palabras normales. Los códigos pueden
quedarse en el log.»

Los motivos del servidor ya explican el porqué con palabras y terminan citando el
criterio entre paréntesis —«Está medida y no tiene fila (C-6).»—. Esa cita sirve en
la web, en las actas y en el registro, y se deja allí. **Aquí sólo se quita lo que
no es más que la cita**: un paréntesis hecho únicamente de códigos (y de
«propuesto» o «firmado»), o un «C-15: » al principio. Nada más se toca: un
paréntesis con otra cosa dentro —«(4,00 m²)»— se queda como está.

Se aplica a la respuesta que recibe el comando (`?formato=lisp`), sólo en las
claves de mensaje: las celdas, los rótulos y las piezas son del plano del
arquitecto y no se tocan aunque algo en ellos se parezca a un código.
"""
from __future__ import annotations

import re
from typing import Any

_CODIGO = r"`?[CD]-\d+`?"
_ESTADO = r"propuest[oa]|firmad[oa]|pendiente de firma|enmienda(?: de)?"
#: Un paréntesis que sólo lleva códigos, separados por comas o «y», con o sin su estado.
_PARENTESIS = re.compile(
    r"\s*\(\s*(?:(?:%s|%s)\s*(?:,|;|\by\b)?\s*)+\)" % (_CODIGO, _ESTADO), re.IGNORECASE)
_PREFIJO = re.compile(r"^\s*%s\s*:\s*" % _CODIGO)

#: Claves cuyos textos son mensajes para el arquitecto.
_MENSAJES = {"motivo", "motivos", "aviso", "avisos", "consejo", "texto", "linea", "tapa",
             "impedimentos", "advertencias", "motivo_sin_estilo", "pregunta", "preguntas",
             "detalle", "nota", "notas", "notas_del_dibujo", "geometria_descartada",
             "motivos_indistinguibles"}
#: Lo que es del plano: ni se mira.
_DEL_PLANO = {"celdas", "filas", "piezas", "recintos", "textos", "rotulos", "rotulo", "vivienda",
              "nombre", "etiqueta", "etiquetas", "capa", "capas", "handle", "textos_a_medir",
              "celdas_escritas"}


def sin_codigos(texto: str) -> str:
    limpio = _PREFIJO.sub("", _PARENTESIS.sub("", texto))
    return limpio


def _es_mensaje(clave: str) -> bool:
    return clave in _MENSAJES or clave.endswith("_aviso") or clave.endswith("_consejo")


def para_el_comando(valor: Any, en_mensaje: bool = False) -> Any:
    """Copia de la respuesta con los mensajes sin códigos."""
    if isinstance(valor, dict):
        res = {}
        for clave, v in valor.items():
            k = str(clave)
            if k in _DEL_PLANO:
                res[clave] = v
            else:
                res[clave] = para_el_comando(v, en_mensaje or _es_mensaje(k))
        return res
    if isinstance(valor, (list, tuple)):
        return [para_el_comando(v, en_mensaje) for v in valor]
    if isinstance(valor, str) and en_mensaje:
        return sin_codigos(valor)
    return valor
