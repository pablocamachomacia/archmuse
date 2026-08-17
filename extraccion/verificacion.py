"""Comprobaciones mecánicas anti-alucinación (§3, puntos 1-4 del diseño).

Ninguna función de este módulo llama a un modelo ni confía en lo que el
modelo dice de sí mismo — todas comparan la salida de la IA contra hechos
verificables: el texto de entrada y los catálogos cerrados ya existentes.

**Única frontera autorizada de `extraccion/` hacia `normativa/`**: importa
`normativa.modelo` (catálogos cerrados en código: tipos, patrones,
prioridades) y `normativa.catalogos`/`normativa.condiciones` (catálogos
cerrados en datos: materias, comparadores). Es exactamente la misma clase de
excepción que ya tiene `analyzer/cte_zonas.py` — reutilizar un vocabulario
cerrado en vez de forkearlo — y `test_extraccion_fronteras.py` vigila que no
se amplíe a nada más (nunca `normativa.loader`, `.validacion`, `.registro`,
`.resolucion`: este módulo no carga corpus ni resuelve nada, solo consulta
vocabulario).
"""
from __future__ import annotations

from typing import Optional, Sequence

from normativa.catalogos import materias
from normativa.condiciones import COMPARADORES, COMPARADORES_DE_PRESENCIA
from normativa.modelo import PATRONES, PRIORIDADES, TIPOS_REGLA

from .modelo import Parametro, Segmento, Señales


def patron_valido(patron: Optional[str]) -> bool:
    return patron is None or patron in PATRONES


def materia_valida(materia: Optional[str]) -> bool:
    return materia is None or materia in materias()


def tipo_valido(tipo: Optional[str]) -> bool:
    return tipo is not None and tipo in TIPOS_REGLA


def severidad_valida(severidad: Optional[str]) -> bool:
    return severidad is None or severidad in PRIORIDADES


def comparador_valido(comparador: Optional[str]) -> bool:
    return comparador is None or comparador in COMPARADORES or comparador in COMPARADORES_DE_PRESENCIA


def tipo_coherente_con_patron(tipo: Optional[str], patron: Optional[str]) -> bool:
    """Misma regla que la validación 3 de `normativa/validacion.py`
    (`validar_evaluabilidad`), reaplicada aquí sobre un borrador en vez de
    sobre un fichero de corpus: evaluable ⟹ tiene patrón; no evaluable ⟹ no
    lo tiene. Un tipo desconocido no es "coherente": es indeterminado, y se
    trata como fallo — más vale una candidata marcada para revisión de más
    que una que pase por coherente sin serlo."""
    if tipo is None or tipo not in TIPOS_REGLA:
        return False
    evaluable = TIPOS_REGLA[tipo]
    tiene_patron = patron is not None
    return evaluable == tiene_patron


def cifras_verificadas_en_texto(parametros: Sequence[Parametro], texto_original: str) -> bool:
    """Todo `valor_citado` debe aparecer, literalmente, en el texto que se le
    pasó a la IA. Es una comprobación de subcadena, no de la IA: un umbral
    que "recuerda" de otra norma pero no está en este artículo se detecta
    aquí, mecánicamente, sin que el modelo tenga que admitirlo.

    Sin parámetros que verificar, no hay nada que pueda haberse inventado —
    `True` vacuamente, no un caso especial."""
    return all(p.valor_citado.strip() and p.valor_citado.strip() in texto_original for p in parametros)


def segmento_correcto(segmento_id_declarado: Optional[str], segmento: Segmento) -> bool:
    """La IA debe devolver el id del segmento que se le pasó, no otro. Es la
    comprobación de que no ha "saltado" a interpretar un artículo distinto
    del que tenía delante — algo que un modelo de lenguaje puede hacer si el
    prompt menciona otros artículos de pasada dentro del propio texto."""
    return segmento_id_declarado == segmento.id


def construir_señales(
    *,
    tipo: Optional[str],
    patron: Optional[str],
    materia: Optional[str],
    severidad: Optional[str],
    parametros: Sequence[Parametro],
    texto_original: str,
    segmento_id_declarado: Optional[str],
    segmento: Segmento,
    necesita_revision_humana: bool,
) -> Señales:
    """Punto de entrada único: de la salida cruda de la IA a las señales que
    `confianza.py` necesita. `pipeline.py` es el único llamador — así el
    orden de comprobación queda en un solo sitio, no repartido."""
    return Señales(
        patron_en_catalogo_cerrado=patron_valido(patron),
        materia_en_catalogo_cerrado=materia_valida(materia),
        tipo_en_catalogo_cerrado=tipo_valido(tipo),
        severidad_en_catalogo_cerrado=severidad_valida(severidad),
        tipo_coherente_con_patron=tipo_coherente_con_patron(tipo, patron),
        cifras_verificadas_en_texto=cifras_verificadas_en_texto(parametros, texto_original),
        segmento_correcto=segmento_correcto(segmento_id_declarado, segmento),
        pide_revision_la_propia_ia=necesita_revision_humana,
    )
