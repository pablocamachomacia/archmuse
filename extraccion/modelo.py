"""Entidades de la Fase 2: `Segmento` (salida de la segmentación determinista)
y `ReglaCandidata` (salida de la interpretación por IA, ya verificada).

`ReglaCandidata` NO es `normativa.modelo.ReglaNormativa` — es su materia
prima, antes de que ningún colegiado la valide. Confundirlas sería el mismo
error que ya se evitó en la Fase 1 con `ingesta.modelo.DocumentoOficial`
frente a `normativa.modelo.NormaFuente`: un borrador no es una regla, por
bien estructurado que la IA lo devuelva.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Segmento:
    """Una unidad direccionable del documento — un artículo o un anejo — con
    su texto literal completo y el contexto jerárquico (capítulo/anejo) en el
    que aparece. Nada de esto usa IA: es partir el XML por sus propias marcas
    de clase (`p.articulo`, `p.anexo_num`...), verificadas contra el CTE real
    (ver `docs/design/2026-08-06-extraccion-cte.md` §0)."""

    id: str  # estable dentro del documento: "articulo_unico", "anejo_i"...
    tipo_segmento: str  # "articulo" | "anejo" | "disposicion"
    titulo: str
    capitulo: Optional[str]
    texto: str  # literal completo, párrafos unidos — lo que ve la IA
    documento_identificador: str
    orden: int  # posición en el documento, para poder citar "el segmento nº N"


# --- Señales mecánicas de verificación --------------------------------------

@dataclass(frozen=True)
class Señales:
    """Los cuatro primeros mecanismos anti-alucinación de §3 del diseño,
    convertidos en datos. `confianza.py` los lee; nunca los recalcula a su
    manera — sería el mismo riesgo de "dos caminos para lo mismo" que ya se
    evitó en la Fase 1 al construir `ContextoTerritorial` por un único
    camino."""

    patron_en_catalogo_cerrado: bool
    materia_en_catalogo_cerrado: bool
    tipo_en_catalogo_cerrado: bool
    severidad_en_catalogo_cerrado: bool
    tipo_coherente_con_patron: bool  # no-evaluable ⟹ sin patrón/parámetro
    cifras_verificadas_en_texto: bool  # todo valor citado aparece en texto_original
    segmento_correcto: bool  # la IA no "saltó" a un artículo que no se le pasó
    pide_revision_la_propia_ia: bool

    def fallos_graves(self) -> Tuple[str, ...]:
        """Lo que nunca puede convivir con confianza Alta. Ver `confianza.py`."""
        graves = []
        if not self.cifras_verificadas_en_texto:
            graves.append("cita una cifra que no aparece en el texto del segmento")
        if not self.tipo_coherente_con_patron:
            graves.append("declara patrón/parámetro en un tipo de regla no evaluable, o al revés")
        if not self.segmento_correcto:
            graves.append("la interpretación no corresponde al segmento que se le pasó")
        if self.pide_revision_la_propia_ia:
            graves.append("el propio modelo marcó necesita_revision_humana")
        return tuple(graves)

    def fallos_menores(self) -> Tuple[str, ...]:
        menores = []
        if not self.patron_en_catalogo_cerrado:
            menores.append("el patrón declarado no es uno de los 5 del catálogo cerrado")
        if not self.materia_en_catalogo_cerrado:
            menores.append("la materia declarada no está en el catálogo cerrado de 14")
        if not self.tipo_en_catalogo_cerrado:
            menores.append("el tipo declarado no es uno de los 7 del catálogo cerrado")
        if not self.severidad_en_catalogo_cerrado:
            menores.append("la severidad declarada no es una de las 4 de la escala existente")
        return tuple(menores)


@dataclass(frozen=True)
class Parametro:
    """Un valor citado en el artículo — cubre "parámetros" y "umbrales" del
    encargo, que son el mismo concepto con o sin comparador.

    Deliberadamente NO es `normativa.modelo.Parametro` (tabla con ejes y
    cadena de repliegue): eso exige criterio del Curador para decidir contra
    qué eje de contexto se indexa, y a veces cruzar varios artículos. Esto es
    solo lo que UN artículo dice, tal como lo dice."""

    nombre: str
    valor_citado: str  # tal cual aparece en el texto, sin normalizar
    unidad: Optional[str]
    comparador: Optional[str]  # del vocabulario cerrado de normativa.condiciones, si aplica
    contexto_citado: Optional[str]  # p.ej. "vivienda unifamiliar", tal como lo dice el artículo


@dataclass(frozen=True)
class ReglaCandidata:
    """Todo lo que pidió el encargo, y nada que no se pueda trazar hasta el
    artículo original. Ver `docs/design/2026-08-06-extraccion-cte.md` §2 para
    la correspondencia de cada campo con el vocabulario ya existente."""

    # --- Trazabilidad hasta el documento oficial ---------------------------
    texto_original: str
    documento: str  # título del documento fuente
    documento_identificador: str  # identificador BOE
    articulo: str
    apartado: Optional[str]
    version: str  # hash_texto del DocumentoOficial de origen
    fecha: Optional[str]
    url_oficial: str
    organismo: str

    # --- Interpretación ------------------------------------------------------
    tipo: Optional[str]  # uno de los 7 catálogo cerrado, o None si indeterminado
    patron: Optional[str]  # uno de los 5, o None
    materia_sugerida: Optional[str]  # "categoría" del encargo
    severidad_sugerida: Optional[str]  # "severidad" del encargo, reutiliza prioridad
    condicion_aplicacion: Optional[str]
    parametros: Tuple[Parametro, ...]
    excepciones: Tuple[str, ...]
    referencias_internas: Tuple[str, ...]  # "dependencias": menciones a otros artículos/anejos
    explicacion_tecnica: str
    explicacion_interpretacion: str  # CÓMO se llegó de texto a estructura, no solo el qué

    # --- Confianza y revisión, mecánicas -------------------------------------
    nivel_confianza: str  # "Alta" | "Media" | "Baja" — nunca un número
    revisar_manualmente: bool
    motivos_revision: Tuple[str, ...]
    señales: Señales

    @property
    def lista_para_promocion(self) -> bool:
        """Nunca es `True` si `revisar_manualmente` lo es. No hay ningún otro
        camino para que una candidata se considere "lista": ni la propia IA
        ni ningún campo de esta clase puede saltarse esta propiedad, porque
        nada en `extraccion/` escribe al corpus — esto es solo la etiqueta
        que una futura Fase 5 (promoción, no construida) tendría que mirar."""
        return not self.revisar_manualmente and self.nivel_confianza == "Alta"
