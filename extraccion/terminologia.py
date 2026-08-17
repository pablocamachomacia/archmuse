# -*- coding: utf-8 -*-
"""Extracción de definiciones terminológicas — determinista, sin IA.

**Por qué este módulo existe separado de `interprete.py`.** El intérprete
convierte un segmento normativo en `ReglaCandidata`: le asigna tipo, patrón,
parámetros y severidad. Aplicado a un anejo de terminología, eso *deformaría*
la definición hasta darle forma de regla evaluable — exactamente lo que
`docs/design/DB-SI_DECISIONS.md` (D5.b) prohíbe. Una definición no se evalúa:
se cita.

Por eso aquí no se llama a ningún modelo. Una definición es una transcripción
literal, y una transcripción no se infiere: se copia. Si el texto no se puede
localizar, este módulo lo dice en vez de aproximarlo.

**Lista explícita de términos, nunca descubrimiento a ciegas.** `extraer_*`
recibe los términos que el Curador quiere transcribir. Se comprobó sobre el
Anejo SI A real que un detector de "líneas que parecen término" produce 4
falsos positivos de 53 (filas de una tabla dentro de «Recorrido de
evacuación»), y un falso positivo no da un término de más: **trunca la
definición anterior**. Con lista explícita, un término que no aparezca falla
de forma ruidosa (`TerminoNoEncontrado`) en lugar de devolver texto a medias.

**Lo que este módulo NO hace, deliberadamente:**

- No corrige los artefactos de extracción del PDF. El texto de origen trae
  espacios espurios dentro de palabras (`ocup able`, `densid ades`,
  `p úblico`). Unirlos exige un diccionario, y eso ya es inferencia sobre el
  literal de una norma. Se transcriben tal cual y quedan a la vista.
- No marca ninguna definición como verificada. `NORMATIVE_ENGINE.md` §12 fija
  la regla de dos personas; una máquina no es la segunda.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


class TerminoNoEncontrado(LookupError):
    """El término pedido no aparece como entrada en el texto dado.

    Es un fallo ruidoso a propósito: la alternativa —devolver la definición
    del término vecino, o un fragmento— es la clase de error que nadie
    detecta leyendo el YAML resultante.
    """


@dataclass(frozen=True)
class DefinicionExtraida:
    """Una entrada de glosario tal como se leyó del documento oficial.

    `literal` es el texto reflujado (ver `_reflujo`), no el crudo del PDF:
    las líneas envueltas se unen y el guionado de fin de línea se deshace,
    porque son artefactos de maquetación y no del texto legal. Cualquier otra
    anomalía se conserva.
    """

    termino: str
    literal: str


# Encabezados de página y numeración que el PDF intercala dentro del anejo.
_RUIDO_DE_PAGINA = re.compile(r"^(Documento B[aá]sico|Anejo [A-Z]\.|SI \d|\d+)")


def _es_linea_de_entrada(linea: str) -> bool:
    """¿Esta línea es la cabecera de una entrada de glosario?

    En el Anejo SI A el término ocupa una línea corta propia y el cuerpo va
    envuelto a ~100 caracteres, así que "línea corta que no cierra frase" es
    una señal fiable. Se usa solo para encontrar **dónde acaba** una
    definición pedida, nunca para decidir qué términos existen.
    """
    s = linea.strip()
    if not (3 <= len(s) <= 60):
        return False
    if not s[:1].isupper() or s.isupper():
        return False
    if s[-1] in ".,:;-)":
        return False
    return not _RUIDO_DE_PAGINA.match(s)


def _reflujo(lineas: Sequence[str]) -> str:
    """Líneas envueltas del PDF -> párrafo continuo.

    Dos normalizaciones, ambas de maquetación y ninguna de contenido:
    se deshace el guionado de fin de línea (`uni-\\nfamiliar` -> `unifamiliar`)
    y se unen las líneas envueltas. Los espacios espurios *dentro* de una
    palabra no se tocan (ver docstring del módulo).
    """
    texto = "\n".join(lineas)
    texto = re.sub(r"-\s*\n\s*", "", texto)
    texto = re.sub(r"\s*\n\s*", " ", texto)
    return re.sub(r"\s{2,}", " ", texto).strip()


def extraer_de_anejo_pdf(texto: str, terminos: Iterable[str]) -> List[DefinicionExtraida]:
    """Definiciones de un anejo de terminología extraído de un PDF.

    `texto` es el cuerpo del segmento de tipo `anejo` que devuelve
    `segmentador_pdf.segmentar` (p. ej. `dbsi_anejo_a`). Cada término se
    localiza por su línea propia y su definición llega hasta la siguiente
    entrada de glosario.
    """
    lineas = texto.split("\n")
    marcas = [i for i, l in enumerate(lineas) if _es_linea_de_entrada(l)]
    por_texto: Dict[str, List[int]] = {}
    for i in marcas:
        por_texto.setdefault(lineas[i].strip(), []).append(i)

    extraidas: List[DefinicionExtraida] = []
    for termino in terminos:
        posiciones = por_texto.get(termino)
        if not posiciones:
            raise TerminoNoEncontrado(
                f"«{termino}» no aparece como entrada de glosario en el texto dado"
            )
        inicio = posiciones[-1]  # el índice repite el término; el cuerpo es la última
        fin = next((m for m in marcas if m > inicio), len(lineas))
        cuerpo = _reflujo(lineas[inicio + 1:fin])
        if not cuerpo:
            raise TerminoNoEncontrado(f"«{termino}» aparece pero su definición está vacía")
        extraidas.append(DefinicionExtraida(termino=termino, literal=cuerpo))
    return extraidas


# En el XML del BOE cada definición es un párrafo propio `Término: cuerpo`,
# estructura mucho más limpia que la del PDF — de ahí una función aparte en
# vez de un parámetro de modo: son dos formatos, no dos ajustes del mismo.
_PARRAFO_BOE = re.compile(r"<p class=\"parrafo\">(.*?)</p>", re.S)
_ETIQUETA = re.compile(r"<[^>]+>")


def extraer_de_anejo_boe(xml: str, terminos: Iterable[str]) -> List[DefinicionExtraida]:
    """Definiciones del Anejo III de la Parte I del CTE, desde el XML del BOE.

    El Anejo SI A remite explícitamente aquí para los términos de uso común
    en el conjunto del Código, así que las dos funciones cubren juntas el
    vocabulario que una regla de DB-SI puede necesitar.
    """
    parrafos = [
        re.sub(r"\s+", " ", _ETIQUETA.sub("", p)).strip()
        for p in _PARRAFO_BOE.findall(xml)
    ]
    extraidas: List[DefinicionExtraida] = []
    for termino in terminos:
        prefijo = termino + ":"
        cuerpo = next(
            (p[len(prefijo):].strip() for p in parrafos if p.startswith(prefijo)),
            None,
        )
        if not cuerpo:
            raise TerminoNoEncontrado(
                f"«{termino}» no aparece como párrafo de definición en el XML dado"
            )
        extraidas.append(DefinicionExtraida(termino=termino, literal=cuerpo))
    return extraidas
