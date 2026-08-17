"""Segmentación determinista del texto PDF de `codigotecnico.org` en
`Segmento`s — mismo contrato de salida que `segmentador.py` (BOE/XML), pero
por regex sobre texto plano en vez de marcas de clase XML, porque
`codigotecnico.org` no publica sus Documentos Básicos en un formato
estructurado (ver `ingesta/fuentes/codigotecnico.py`).

Cero IA. Cero red. Verificado contra el DB-SI real (92 páginas,
`_scratch_dbsi.pdf` de la sesión de auditoría), no supuesto de memoria.

**Estructura real de un DB** (distinta de un artículo del BOE):

    Sección {CODIGO} N   Título      -> como `capitulo_tit` en el XML: NO es
                                         un segmento propio, es el contexto
                                         de los apartados que siguen
    N Título del apartado            -> el segmento (equivalente a
                                         "artículo"): un apartado numerado
                                         dentro de una Sección
    Anejo {letra} Título             -> un segmento propio, sin dividir en
                                         sus propios puntos internos (B.1,
                                         B.2...) — mismo alcance que
                                         `segmentador.py` ya acepta para los
                                         anejos del BOE, no una limitación
                                         nueva de este módulo.

**El problema real y cómo se resuelve**: un apartado nuevo ("3 Espacios
ocultos...") y un párrafo normativo dentro del apartado anterior ("1 La
compartimentación...") tienen el mismo aspecto por regex — ambos son
"número + texto" al principio de línea. Un solo apartado no se puede
detectar de forma fiable mirando solo esa línea. Se usan DOS señales
independientes a la vez, tomadas del propio Índice del documento (que sí
sirve de referencia inequívoca, verificado que aparece en todo DB real):

1. el número coincide con "el siguiente apartado esperado" dentro de esa
   Sección (secuencial: 1, 2, 3... nunca se reinicia dentro de una Sección,
   a diferencia de los párrafos internos que si reinician en 1 en cada
   apartado nuevo);
2. el texto que sigue es muy parecido (`_similar`, sobre texto normalizado
   sin espacios ni tildes) al título de ese apartado tal como aparece en el
   Índice.

Ninguna de las dos por separado basta (un párrafo interno también podría,
por casualidad, empezar por el número correcto) — juntas, sí: la
probabilidad de que un párrafo cualquiera tenga además un texto casi
idéntico al título real del siguiente apartado es la que hace la señal
fiable, no cada mitad por separado.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from ingesta.modelo import DocumentoOficial

from .modelo import Segmento

_UMBRAL_SIMILITUD = 0.82  # elegido tras verificar contra DB-SI real: los pares título-índice/título-cuerpo genuinos superan 0.9 pese a los artefactos de extracción; nada espurio se acercó a 0.82 en esa misma corrida


@dataclass(frozen=True)
class _EntradaIndice:
    numero: str  # "1", "2"... dentro de la Sección; o la letra ("A", "B"...) para un Anejo
    titulo: str


@dataclass(frozen=True)
class _Seccion:
    numero: str
    titulo: str
    apartados: Tuple[_EntradaIndice, ...]


def _normalizar(texto: str) -> str:
    """Sin tildes, sin espacios, en minúsculas, uniendo palabras partidas por
    guion de justificación ("in stalaciones" / "compartimentaci-\\nón"). Es
    lo que hace comparable un título extraído en el Índice (una línea) con el
    mismo título extraído en el cuerpo (envuelto de otra forma, con espacios
    fantasma distintos) — mismo texto, extracción independiente, forma
    distinta; solo la versión sin espacios es estable entre las dos."""
    sin_guiones = re.sub(r"-\s*\n\s*", "", texto)
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", sin_guiones) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def _titulo_coincide(candidato: str, esperado: str) -> bool:
    """`candidato` (texto del cuerpo, con líneas de más allá del título
    real capturadas "por si acaso" — ver `_apartados_de_seccion`) coincide
    con `esperado` (título tal como lo declara el Índice) si el segundo
    aparece contenido en el primero una vez normalizados. Contención, no
    `_similar` a secas: un candidato más largo que el título real (porque
    incluyó de más una línea de cuerpo que no era título) no debe penalizar
    la coincidencia — solo importa que el título esperado esté ahí dentro.
    `_similar` como respaldo cubre el caso contrario, título envuelto que
    el candidato capturó de menos."""
    c, e = _normalizar(candidato), _normalizar(esperado)
    if not e:
        return False
    if e in c:
        return True
    return _similar(candidato, esperado) >= _UMBRAL_SIMILITUD


def _slug(*partes: str) -> str:
    return "_".join(_normalizar(p) or "x" for p in partes)


# --- Localizar el Índice y separar cuerpo -----------------------------------

# `[ \t]` (nunca `\s`) entre dos tokens del MISMO renglón lógico: `\s` incluye
# `\n`, así que un `\s+` ahí podría saltar por encima de un salto de línea —
# y en concreto, por encima de un número de página suelto en su propia línea
# ("9\n \n2 Accesibilidad por fachada") fusionándolo con el título siguiente.
# Encontrado de verdad contra el Índice real del DB-SI (Sección SI 5), no
# una precaución teórica — ver el commit/test que lo cubre.
_RE_PAGINA_INDICE = re.compile(r"^\s*[IÍ]NDICE\s*$", re.MULTILINE)
_RE_SECCION_INDICE = re.compile(r"^[ \t]*Secci[oó]n[ \t]+(\S+)[ \t]+(\d+)[ \t]{2,}(.+?)\s*$", re.MULTILINE)
_RE_ANEJO_INDICE = re.compile(r"^[ \t]*Anejo[ \t]+\S+[ \t]+([A-Z])[ \t]+(.+?)\s*$", re.MULTILINE)
_RE_APARTADO_INDICE = re.compile(r"^[ \t]*(\d+)[ \t]+(\S.*?)\s*$", re.MULTILINE)

# Solo el número: a diferencia del Índice (una línea: "Sección SI 1   Título"),
# en el cuerpo el título a veces envuelve a la línea siguiente ("Sección SI 1
# \nPropagación interior \n") — verificado contra el DB-SI real. Por eso el
# título de Sección se valida igual que un apartado: contra el Índice, no se
# asume de esta línea.
_RE_SECCION_CUERPO = re.compile(r"^[ \t]*Secci[oó]n[ \t]+\S+[ \t]+(\d+)[ \t]*$", re.MULTILINE)
# El código del DB antes de la letra ("Anejo SI A...") es inconsistente entre
# anejos del mismo documento — verificado contra el DB-SI real: unos lo
# llevan ("Anejo SI A Terminología", "Anejo SI E...") y otros no ("Anejo B
# Tiempo...", "Anejo D Resistencia..."). El grupo opcional cubre ambas
# formas. La cabecera de página repetida ("Anejo A. Terminología", con
# punto) queda fuera a propósito: tras la letra exige un espacio, no un
# punto, así que nunca compite como falso encabezado real.
_RE_ANEJO_CUERPO = re.compile(r"^[ \t]*Anejo[ \t]+(?:\S+[ \t]+)?([A-Z])[ \t]+(.+?)\s*$", re.MULTILINE)
_RE_APARTADO_CUERPO = re.compile(r"^[ \t]*(\d+)[ \t]+(\S.*?)\s*$", re.MULTILINE)


def _paginas(documento: DocumentoOficial) -> List[str]:
    # `\f` (form feed) es el separador que `codigotecnico.py` inserta entre
    # páginas al extraer el PDF — ver su docstring.
    return documento.texto_crudo.split("\f")


def _es_pagina_indice(pagina: str) -> bool:
    lineas = [l for l in pagina.splitlines() if l.strip()]
    # La cabecera repetida ("Documento Básico SI...") ocupa la 1ª línea; la
    # 2ª es el título de página en TODAS las páginas de este documento —
    # verificado contra el DB-SI real (`ÍNDICE` en pág. 7-8, `SI 1. Prop...`
    # en el cuerpo). Sin esa 2ª línea (página en blanco, portada) no es Índice.
    return len(lineas) > 1 and bool(_RE_PAGINA_INDICE.match(lineas[1].strip()))


def _parsear_indice(texto_indice: str) -> Tuple[List[_Seccion], List[_EntradaIndice]]:
    """Devuelve (secciones con sus apartados, anejos) tal como los declara el
    propio Índice del documento — la referencia contra la que se valida el
    cuerpo, no una lista inventada por este módulo."""
    marcas: List[Tuple[int, str, tuple]] = []
    for m in _RE_SECCION_INDICE.finditer(texto_indice):
        marcas.append((m.start(), "seccion", (m.group(2), m.group(3))))
    for m in _RE_ANEJO_INDICE.finditer(texto_indice):
        marcas.append((m.start(), "anejo", (m.group(1), m.group(2))))
    marcas.sort(key=lambda t: t[0])

    secciones: List[_Seccion] = []
    anejos: List[_EntradaIndice] = []
    seccion_actual: Optional[dict] = None

    for i, (inicio, tipo, datos) in enumerate(marcas):
        fin = marcas[i + 1][0] if i + 1 < len(marcas) else len(texto_indice)
        if tipo == "seccion":
            if seccion_actual is not None:
                secciones.append(_Seccion(seccion_actual["numero"], seccion_actual["titulo"], tuple(seccion_actual["apartados"])))
            seccion_actual = {"numero": datos[0], "titulo": datos[1], "apartados": []}
            bloque = texto_indice[inicio:fin]
            # Los apartados de esta Sección son las líneas "N Título" dentro
            # de su propio bloque, excluyendo la propia línea de cabecera de
            # Sección (que también empieza distinto: "Sección", no un dígito).
            primera_linea_saltada = bloque.split("\n", 1)[1] if "\n" in bloque else ""
            candidatos = list(_RE_APARTADO_INDICE.finditer(primera_linea_saltada))
            for j, am in enumerate(candidatos):
                titulo = am.group(2)
                # Título envuelto a una 2ª línea física ("...de i n-\ncendios"):
                # se anexa SOLO si esa línea no es a su vez el arranque de la
                # siguiente entrada numerada — si lo es, no hay nada que
                # anexar. Mismo criterio de lookahead que ya usa
                # `_apartados_de_seccion` en el cuerpo, aplicado aquí al
                # Índice — verificado contra el DB-SI real (Sección SI 1,
                # apartado 3, que envuelve; el resto de esta Sección no).
                fin_linea_actual = primera_linea_saltada.find("\n", am.end())
                inicio_siguiente = fin_linea_actual + 1 if fin_linea_actual != -1 else len(primera_linea_saltada)
                fin_siguiente = primera_linea_saltada.find("\n", inicio_siguiente)
                fin_siguiente = fin_siguiente if fin_siguiente != -1 else len(primera_linea_saltada)
                siguiente_linea = primera_linea_saltada[inicio_siguiente:fin_siguiente].strip()
                si_hay_siguiente_entrada = j + 1 < len(candidatos) and candidatos[j + 1].start() < fin_siguiente
                # Un subpunto propio del Índice ("4.1 Criterios...", listado
                # bajo el apartado "4") tampoco es continuación de su título
                # — mismo motivo que arriba, con un patrón distinto porque
                # `_RE_APARTADO_INDICE` no lo reconoce como entrada propia
                # (exige que tras el número venga un espacio, no un punto).
                if re.match(r"^\d+\.\d", siguiente_linea):
                    siguiente_linea = ""
                if siguiente_linea and not si_hay_siguiente_entrada:
                    titulo = f"{titulo} {siguiente_linea}"
                seccion_actual["apartados"].append(_EntradaIndice(am.group(1), titulo))
        else:  # anejo
            anejos.append(_EntradaIndice(datos[0], datos[1]))

    if seccion_actual is not None:
        secciones.append(_Seccion(seccion_actual["numero"], seccion_actual["titulo"], tuple(seccion_actual["apartados"])))

    return secciones, anejos


# --- Segmentar el cuerpo usando el Índice como referencia -------------------

def _apartados_de_seccion(
    cuerpo: str, inicio: int, fin: int, seccion: _Seccion, codigo: str, orden_inicial: int
) -> Tuple[List[Segmento], int]:
    esperados = list(seccion.apartados)
    if not esperados:
        return [], orden_inicial

    segmentos: List[Segmento] = []
    orden = orden_inicial
    siguiente_esperado = 0  # índice en `esperados`
    pendiente: Optional[dict] = None

    candidatos = list(_RE_APARTADO_CUERPO.finditer(cuerpo, inicio, fin))
    for m in candidatos:
        if siguiente_esperado >= len(esperados):
            break
        entrada = esperados[siguiente_esperado]
        numero_linea = m.group(1)
        # Título candidato: el resto de esta línea + las 2 siguientes (un
        # título de apartado puede envolver a 2 líneas más, no solo 1 —
        # verificado contra el DB-SI real, apartado "3" de la Sección SI 1:
        # "Espacios ocultos. Paso de instalaciones a través de elementos" +
        # "de compartimentación de incendios"). De más no penaliza: se
        # compara por contención (`_titulo_coincide`), no por igualdad de
        # longitud — capturar alguna línea de sobra es más seguro que
        # quedarse corto y no reconocer el apartado.
        cursor_lookahead = m.end()
        lineas_extra = []
        for _ in range(2):
            salto = cuerpo.find("\n", cursor_lookahead)
            limite = salto if salto != -1 and salto <= fin else fin
            lineas_extra.append(cuerpo[cursor_lookahead:limite])
            if salto == -1 or salto > fin:
                break
            cursor_lookahead = salto + 1
        titulo_candidato = (m.group(2) + " " + " ".join(lineas_extra)).strip()

        if numero_linea == entrada.numero and _titulo_coincide(titulo_candidato, entrada.titulo):
            # Cierra el apartado anterior (todo el texto hasta aquí) y abre este.
            if pendiente is not None:
                cuerpo_previo = cuerpo[pendiente["desde"]:m.start()].strip()
                if cuerpo_previo:
                    segmentos.append(Segmento(
                        id=pendiente["id"], tipo_segmento="apartado", titulo=pendiente["titulo"],
                        capitulo=pendiente["capitulo"], texto=cuerpo_previo,
                        documento_identificador=pendiente["documento_identificador"], orden=pendiente["orden"],
                    ))
            orden += 1
            pendiente = {
                "id": _slug(codigo, "sec", seccion.numero, "pt", entrada.numero),
                "titulo": f"{codigo} {seccion.numero}.{entrada.numero} {entrada.titulo}",
                "capitulo": f"Sección {codigo} {seccion.numero}: {seccion.titulo}",
                "desde": m.start(),
                "documento_identificador": codigo,
                "orden": orden,
            }
            siguiente_esperado += 1

    if pendiente is not None:
        cuerpo_previo = cuerpo[pendiente["desde"]:fin].strip()
        if cuerpo_previo:
            segmentos.append(Segmento(
                id=pendiente["id"], tipo_segmento="apartado", titulo=pendiente["titulo"],
                capitulo=pendiente["capitulo"], texto=cuerpo_previo,
                documento_identificador=pendiente["documento_identificador"], orden=pendiente["orden"],
            ))

    return segmentos, orden


def segmentar(documento: DocumentoOficial) -> List[Segmento]:
    """El documento oficial completo -> sus apartados (por Sección) y sus
    anejos, en el orden en que aparecen. Un documento sin Índice reconocible
    o sin ninguna Sección/Anejo detectada devuelve una lista vacía — no es un
    error, es un documento sin la estructura que este módulo sabe reconocer
    (ver limitaciones en `docs/design/`), y quien llame decide qué hacer."""
    codigo = documento.identificador  # p.ej. "DB-SI"
    paginas = _paginas(documento)

    paginas_indice = [p for p in paginas if _es_pagina_indice(p)]
    if not paginas_indice:
        return []
    texto_indice = "\n".join(paginas_indice)
    secciones, anejos_indice = _parsear_indice(texto_indice)
    if not secciones and not anejos_indice:
        return []

    # El cuerpo es todo lo que va DESPUÉS de la última página de Índice —
    # antes de eso (portada, disposiciones generales) queda fuera de esta
    # primera pasada, ver docstring del módulo.
    ultima_pagina_indice = max(i for i, p in enumerate(paginas) if _es_pagina_indice(p))
    cuerpo = "\f".join(paginas[ultima_pagina_indice + 1:])

    segmentos: List[Segmento] = []
    orden = 0

    marcas_seccion = list(_RE_SECCION_CUERPO.finditer(cuerpo))
    marcas_anejo = list(_RE_ANEJO_CUERPO.finditer(cuerpo))

    for i, m in enumerate(marcas_seccion):
        numero = m.group(1)
        seccion = next((s for s in secciones if s.numero == numero), None)
        if seccion is None:
            continue
        fin = marcas_seccion[i + 1].start() if i + 1 < len(marcas_seccion) else (marcas_anejo[0].start() if marcas_anejo else len(cuerpo))
        nuevos, orden = _apartados_de_seccion(cuerpo, m.end(), fin, seccion, codigo, orden)
        segmentos.extend(nuevos)

    anejos_por_letra: Dict[str, str] = {e.numero: e.titulo for e in anejos_indice}
    for i, m in enumerate(marcas_anejo):
        letra = m.group(1)
        if letra not in anejos_por_letra:
            continue  # línea que parece "Anejo X ..." pero no está en el Índice: probablemente una referencia cruzada dentro de un párrafo, no un encabezado real
        fin = marcas_anejo[i + 1].start() if i + 1 < len(marcas_anejo) else len(cuerpo)
        texto_anejo = cuerpo[m.end():fin].strip()
        if not texto_anejo:
            continue
        orden += 1
        segmentos.append(Segmento(
            id=_slug(codigo, "anejo", letra), tipo_segmento="anejo",
            titulo=f"Anejo {codigo} {letra} {anejos_por_letra[letra]}",
            capitulo=None, texto=texto_anejo,
            documento_identificador=codigo, orden=orden,
        ))

    return segmentos
