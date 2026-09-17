# -*- coding: utf-8 -*-
"""`C-8` para el número de unidades: lo que el plano declara junto al rótulo de la vivienda.

PRD `docs/prd/2026-09-17-modo-preguntar.md`, D-9 (**propuesta, pendiente de firma**).

`C-8` (firmado el 2026-09-11): lo que el plano declara manda sobre lo que ArchMuse
deduce. El número de unidades **no se deduce de nada**: o el plano lo escribe, o la
celda `NUMERO UDS` queda vacía con motivo. Nunca se cuenta cuántos rótulos iguales hay
(eso sería deducirlo, y en el plano maestro los tipos se dibujan una vez y se repiten
en otras plantas).

**Dónde lo escribe el plano, medido en el maestro (copia local, fuera del
repositorio):** 25 textos sueltos «8uds.», «1 ud.», «3 uds.», en la misma capa que el
rótulo de su tipo, a 1,5-1,7 alturas de texto por debajo; el rótulo de otro tipo, a más
de 13 m. Y la forma que dio Pablo, dentro del propio rótulo: «VT1/3 8 uds».

**Las dos formas que se leen:**

1. **En el rótulo:** «VT1/3 8 uds», «VT1/3 - 8 uds.», «VT1/3 (8 uds)», «VT1/3: 1 ud.»,
   «VT1/3\\P8 uds» (MTEXT en dos líneas). Entre el tipo y el número tiene que haber un
   espacio o un signo: «VT1/38 uds» no dice si es «VT1/3» con 8 o «VT1/38».
2. **En un texto suelto que sólo dice eso** («8uds.», «1 ud.», «12 unidades») a menos
   de `ALCANCE_EN_ALTURAS` alturas del rótulo y **más cerca de él que de cualquier otro
   rótulo de vivienda**.

**Nunca se elige:** con dos declaraciones que no dicen lo mismo —dos textos al alcance
con números distintos, o el rótulo diciendo una cifra y el texto de al lado otra—, la
celda queda vacía y el motivo lo dice. Un cero no es un número de viviendas.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

#: Hasta dónde se busca el texto suelto: 3 alturas del rótulo, las mismas que usa
#: `C-12` para su rótulo (decisión D-9, pendiente de firma). Medido: 1,5-1,7.
ALCANCE_EN_ALTURAS = 3

_UNIDAD = r"(?:uds?|unidad(?:es)?)"
#: El número dentro del rótulo, separado del tipo por espacio o signo.
_EN_EL_ROTULO = re.compile(
    r"^\s*VT\s*\d+(?:\s*/\s*\d+)?(?:\s+|\s*[-–—:,;(\[]\s*)(\d+)\s*" + _UNIDAD + r"\.?\s*[)\]]?\s*$",
    re.IGNORECASE)
#: Un texto que sólo dice el número de unidades.
_SUELTO = re.compile(r"^\s*(\d+)\s*" + _UNIDAD + r"\.?\s*$", re.IGNORECASE)

MOTIVO_SIN_ROTULO = ("la vivienda no tiene rótulo del que leer el número de unidades, y no se "
                     "cuenta (C-8).")
MOTIVO_NO_DECLARA = ("el plano no declara el número de unidades junto al rótulo de esta "
                     "vivienda, y no se cuenta (C-8).")
MOTIVO_SIN_ALTURA = ("el rótulo de la vivienda no trae altura de texto, y sin ella no se sabe "
                     "hasta dónde buscar su número de unidades (C-8).")


@dataclass(frozen=True)
class TextoDelPlano:
    texto: str
    punto: Tuple[float, float]        # en unidades de dibujo
    altura: Optional[float]           # en unidades de dibujo; `None` si no la trae


def textos_del_plano(doc, desplazamiento: Optional[Tuple[float, float]] = None) -> List[TextoDelPlano]:
    """Los TEXT y MTEXT del plano (bloques incluidos, sin lo dibujado por ArchMuse), con
    el mismo recorrido y el mismo punto que `parser.extract_labels`."""
    from . import parser
    from .geometria_recibida import altura_de_texto
    from .propio import es_capa_de_archmuse

    dx, dy = desplazamiento or (0.0, 0.0)
    salida: List[TextoDelPlano] = []
    for entidad, capa in parser._recorrer_plano(doc):
        if entidad.dxftype() not in ("TEXT", "MTEXT") or es_capa_de_archmuse(capa):
            continue
        texto = parser._texto_de(entidad)
        punto = parser._punto_de_texto(entidad)
        if not texto or punto is None:
            continue
        try:
            altura = altura_de_texto(entidad)
        except Exception:  # noqa: BLE001 - entidad virtual de un bloque
            altura = None
        salida.append(TextoDelPlano(texto, (punto[0] + dx, punto[1] + dy), altura))
    return salida


def en_el_rotulo(texto: Optional[str]) -> Optional[int]:
    """El número de unidades escrito dentro del rótulo, o `None`."""
    encontrado = _EN_EL_ROTULO.match(" ".join((texto or "").split()))
    return int(encontrado.group(1)) if encontrado else None


def suelto(texto: Optional[str]) -> Optional[int]:
    """El número de un texto que sólo dice «N uds.», o `None`."""
    encontrado = _SUELTO.match(" ".join((texto or "").split()))
    return int(encontrado.group(1)) if encontrado else None


def sin_unidades(nombre: str) -> str:
    """El rótulo sin su número de unidades: «VT1/3 8 uds» → «VT1/3». Para la celda
    `VIVIENDA TIPO`, que no tiene que repetir lo que va en `NUMERO UDS`."""
    if en_el_rotulo(nombre) is None:
        return nombre
    return re.sub(r"(?:\s+|\s*[-–—:,;(\[]\s*)\d+\s*" + _UNIDAD + r"\.?\s*[)\]]?\s*$", "",
                  " ".join(nombre.split()), flags=re.IGNORECASE)


def numero_de_unidades(textos: Sequence[TextoDelPlano], rotulo_texto: str,
                       rotulo_punto: Optional[Tuple[float, float]]) -> Tuple[str, Optional[str]]:
    """`(valor, motivo)` de la celda `NUMERO UDS`. `rotulo_punto` en unidades de dibujo."""
    from .parser import UNIT_LABEL_PATTERN

    if rotulo_punto is None:
        return "", MOTIVO_SIN_ROTULO
    declarados: List[Tuple[int, str]] = []
    dentro = en_el_rotulo(rotulo_texto)
    if dentro is not None:
        declarados.append((dentro, "el rótulo"))

    rotulos = [t for t in textos if UNIT_LABEL_PATTERN.match(t.texto)]
    propio = min(rotulos, key=lambda t: math.dist(t.punto, rotulo_punto), default=None)
    if propio is not None and math.dist(propio.punto, rotulo_punto) > 1e-6 * max(
            1.0, abs(rotulo_punto[0]), abs(rotulo_punto[1])):
        propio = None
    altura = propio.altura if propio is not None else None
    candidatos = [(n, t) for t, n in ((t, suelto(t.texto)) for t in textos) if n is not None]
    if candidatos and altura is None and dentro is None:
        return "", MOTIVO_SIN_ALTURA
    if altura is not None:
        alcance = ALCANCE_EN_ALTURAS * altura
        for numero, texto in candidatos:
            distancia = math.dist(texto.punto, rotulo_punto)
            if distancia > alcance:
                continue
            otros = [math.dist(texto.punto, r.punto) for r in rotulos if r is not propio]
            if any(d <= distancia for d in otros):
                continue
            declarados.append((numero, "«%s»" % texto.texto))

    if not declarados:
        return "", MOTIVO_NO_DECLARA
    if len({n for n, _donde in declarados}) > 1:
        return "", ("el plano declara números de unidades distintos para esta vivienda (%s): no "
                    "se elige ninguno (C-8)." % ", ".join("%d en %s" % (n, donde)
                                                         for n, donde in declarados))
    numero = declarados[0][0]
    if numero < 1:
        return "", "el plano declara 0 unidades, y eso no es un número de viviendas (C-8)."
    return str(numero), None
