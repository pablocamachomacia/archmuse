"""Segmentación determinista — ruta B, motor de texto distinto.

Prompt 2 (`docs/prd/2026-08-21-verificacion-doble-del-corpus.md`), addendum
de Pablo: "la segunda ruta de extracción DEBE usar un motor de texto PDF
distinto al de la primera, con tratamiento explícito del guionizado de fin
de línea".

La ruta A extrae texto con `pypdf`
(`ingesta/fuentes/codigotecnico.py::_texto_desde_pdf`). Esta ruta usa
`pdfminer.six` — ya presente en el árbol de dependencias como transitiva
(`requirements.lock.txt`), cero coste de instalación nueva — porque su
análisis de layout por posición de carácter es un algoritmo genuinamente
distinto al de `pypdf`, no una reimplementación con otro nombre. Medido
contra el PDF real de DB-SUA (`docs/prd/2026-08-21-verificacion-doble-del-
corpus.md` §5.1): 35/40 parámetros localizables, frente a 18/40 con
`pypdf`. El guionizado de `pdfminer.six` en este documento es guionizado
real de fin de línea («pavimen-\\nto»), no la corrupción de espacios que
produce `pypdf` («p avimen-\\nto») — por eso un des-guionizado simple
funciona aquí y no habría funcionado sobre el texto de la ruta A.

**No reimplementa la segmentación.** Extrae su propio texto por página y
delega TODO lo demás —parseo de índice, detección de apartados, anejos— a
`segmentador_pdf.segmentar`, construyendo un `DocumentoOficial` equivalente
con `texto_crudo` sustituido. Es la misma composición que
`extraccion/pipeline.py::extraer` ya hace posible con su parámetro
`segmentador` inyectable: ese punto de extensión existe precisamente para
esto, no hay que tocar `pipeline.py` para usarlo.

**Un segundo tratamiento, descubierto al probar contra el PDF real, no
anticipado en el PRD.** `pdfminer.six` separa el número de un apartado de
su título en dos líneas distintas cuando el documento los dibuja como dos
objetos de texto separados (habitual en el cuerpo de este PDF, no en su
Índice): la línea sale como

    Resbaladicidad de los suelos

    1
    1  Con el fin de limitar el riesgo de resbalamiento...

en vez de `1 Resbaladicidad de los suelos` (lo que `pypdf` sí concatena en
una sola línea, y lo que `segmentador_pdf.py::_RE_APARTADO_CUERPO` espera).
Sin corregirlo, `segmentador_pdf.segmentar` no reconocía NINGÚN apartado —
0 segmentos sobre el DB-SUA real. `_reconstruir_numero_de_apartado` repara
este patrón (título → número suelto → párrafo 1, sea cual sea el número
con el que reinicia ese párrafo): mueve el número a la línea del título
que lo precede y borra la línea suelta.

**Límite real, medido, no oculto: 15/20 apartados de DB-SUA (75%), no
20/20.** El mismo documento usa TAMBIÉN el orden inverso en algunos
apartados —número suelto ANTES de su título, no después (Sección SUA 2:
«Sección SUA 2 / Seguridad frente al riesgo… / 1 / Impacto / 1.1 /
Impacto con elementos fijos / 1 La altura libre…»)— que
`_reconstruir_numero_de_apartado` no reconoce todavía: intentar
distinguir ambos órdenes de forma genérica sin arriesgar fusionar el
número con la línea equivocada (ocurrió en las primeras pruebas: fusionó
un «1» con el título de la SECCIÓN en vez de con «Impacto») se dejó fuera
de este PRD en vez de forzarlo. Apartados que se quedan sin segmentar por
esto: **1.5, 2.1, 2.2, 8.1, 8.2** (verificado contra las candidatas reales
de la ruta A, `tests/test_segmentador_pdf_b.py`). Para esos, la ruta B no
aporta lectura — la sub-candidata de la ruta A sigue exactamente donde
estaba, sin promoción automática, tal como exige el diseño «si una ruta no
ancla, no se inventa una coincidencia» (§5.3 del PRD).
"""
from __future__ import annotations

import dataclasses
import re
from io import BytesIO
from typing import List

from ingesta.modelo import DocumentoOficial

from . import segmentador_pdf
from .modelo import Segmento

#: Une una palabra partida por guionizado de fin de línea («pavimen-\nto» ->
#: «pavimento»). Deliberadamente simple —no intenta reparar ningún otro tipo
#: de corrupción del PDF— porque es lo único que el guionizado real de
#: `pdfminer.six` necesita; ver el docstring del módulo para la comparación
#: con `pypdf`, cuya corrupción esto NO habría arreglado.
_RE_GUION_FIN_DE_LINEA = re.compile(r"(\w)-\s+(\w)")

#: Una línea que es SOLO un número de apartado (1-2 dígitos), nada más.
_RE_LINEA_SOLO_NUMERO = re.compile(r"^\s*(\d{1,2})\s*$")


#: Longitud máxima de una línea de título plausible. Un párrafo real no
#: cabe aquí — es lo que evita confundir un número de apartado suelto con
#: un número de página suelto al final de una página, que deja detrás un
#: bloque de líneas en blanco y el salto de página, nunca contenido nuevo
#: dentro de la misma página.
_MAX_LONGITUD_TITULO = 100


def _reconstruir_numero_de_apartado(texto: str) -> str:
    """Repara el patrón descrito en el docstring del módulo: una línea que
    es solo «N», seguida (más adelante, en la misma página) de contenido
    real — nunca solo líneas en blanco hasta el final de la página, que es
    la forma de un número de página suelto, no de un marcador de apartado
    — se borra y su número se antepone a la línea anterior no vacía y
    corta (el título). El número que sigue al hueco NO tiene que coincidir
    con «N»: el párrafo 1 de un apartado reinicia su propia numeración
    («2 Discontinuidades… / 2 / 1 Excepto…» — el «1» final es el párrafo,
    no el apartado). Si la línea anterior ya empieza por un número o es
    demasiado larga para ser un título, no se toca."""
    lineas = texto.split("\n")
    n = len(lineas)
    for i in range(n):
        m = _RE_LINEA_SOLO_NUMERO.match(lineas[i])
        if not m:
            continue
        numero = m.group(1)

        j = i + 1
        while j < n and not lineas[j].strip():
            j += 1
        if j >= n:
            continue  # solo blancos hasta el final de la página: número de página

        k = i - 1
        while k >= 0 and not lineas[k].strip():
            k -= 1
        if k < 0 or re.match(r"^\s*\d", lineas[k]) or len(lineas[k].strip()) > _MAX_LONGITUD_TITULO:
            continue

        lineas[k] = numero + " " + lineas[k].lstrip()
        lineas[i] = ""
    return "\n".join(lineas)


def _texto_por_paginas(crudo: bytes) -> List[str]:
    """Una página = un elemento, en el mismo orden que las ve `pypdf` — el
    segmentador existente divide por `\\f` (form feed), y esto tiene que
    producir la misma forma para poder reutilizarlo sin tocarlo."""
    from pdfminer.high_level import extract_pages  # noqa: PLC0415
    from pdfminer.layout import LTTextContainer  # noqa: PLC0415

    paginas = []
    for layout in extract_pages(BytesIO(crudo)):
        texto = "".join(
            elemento.get_text() for elemento in layout
            if isinstance(elemento, LTTextContainer)
        )
        texto = _RE_GUION_FIN_DE_LINEA.sub(r"\1\2", texto)
        texto = _reconstruir_numero_de_apartado(texto)
        paginas.append(texto)
    return paginas


def segmentar(documento: DocumentoOficial) -> List[Segmento]:
    """Mismo contrato que `segmentador_pdf.segmentar`
    (`DocumentoOficial -> List[Segmento]`): esta función es la que se pasa a
    `extraccion.pipeline.extraer(documento, segmentador=...)` cuando se
    quiere la ruta B en vez de la A.

    Exige `documento.bytes_crudos` — el PDF original tal cual se descargó
    (`ingesta/modelo.py::DocumentoOficial`). Sin él no hay texto propio que
    extraer: no se cae de vuelta al `texto_crudo` de la ruta A, porque eso
    dejaría de ser una segunda ruta y pasaría a ser la primera con un
    nombre distinto.
    """
    if not documento.bytes_crudos:
        raise ValueError(
            f"{documento.identificador}: sin `bytes_crudos` (el PDF original). "
            f"La ruta B no puede improvisar con el texto de la ruta A — "
            f"eso dejaría de ser una segunda ruta independiente."
        )
    texto_b = "\f".join(_texto_por_paginas(documento.bytes_crudos))
    documento_b = dataclasses.replace(documento, texto_crudo=texto_b)
    return segmentador_pdf.segmentar(documento_b)
