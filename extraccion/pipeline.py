"""Orquesta los cuatro pasos: segmentar (determinista) → interpretar (IA) →
verificar (determinista) → calcular confianza (determinista). Un único sitio
donde el orden importa, para que no se pueda construir una `ReglaCandidata`
saltándose la verificación por accidente en otro punto del código.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from ingesta.modelo import DocumentoOficial

from . import confianza as _confianza
from . import interprete as _interprete
from . import segmentador as _segmentador
from . import verificacion as _verificacion
from .errores import ErrorDeInterpretacion
from .modelo import Parametro, ReglaCandidata, Segmento


@dataclass(frozen=True)
class ResultadoExtraccion:
    """Igual que `ingesta.modelo.ResultadoIngesta`: no solo lo que salió
    bien. Cuántos segmentos había, cuántos se interpretaron, y los avisos de
    los que no se pudieron interpretar — un resultado que solo contara
    éxitos escondería justo lo que alguien revisando la corrida necesita ver."""

    segmentos_totales: int
    candidatas: Tuple[ReglaCandidata, ...]
    avisos: Tuple[str, ...] = field(default_factory=tuple)

    def por_confianza(self, nivel: str) -> Tuple[ReglaCandidata, ...]:
        return tuple(c for c in self.candidatas if c.nivel_confianza == nivel)

    def listas_para_promocion(self) -> Tuple[ReglaCandidata, ...]:
        """Nunca se usa para promover nada — `extraccion/` no escribe en
        `normativa/es/`. Es la etiqueta que una futura Fase 5 tendría que
        leer, expuesta aquí para que se pueda inspeccionar sin recorrer la
        lista a mano en cada sitio que la necesite."""
        return tuple(c for c in self.candidatas if c.lista_para_promocion)


def _parametro_desde_bruto(bruto: dict) -> Parametro:
    return Parametro(
        nombre=str(bruto.get("nombre", "")),
        valor_citado=str(bruto.get("valor_citado", "")),
        unidad=bruto.get("unidad"),
        comparador=bruto.get("comparador"),
        contexto_citado=bruto.get("contexto_citado"),
    )


def _candidata_desde_bruto(bruto: dict, segmento: Segmento, documento: DocumentoOficial) -> ReglaCandidata:
    parametros = tuple(_parametro_desde_bruto(p) for p in (bruto.get("parametros") or []))

    señales = _verificacion.construir_señales(
        tipo=bruto.get("tipo"),
        patron=bruto.get("patron"),
        materia=bruto.get("materia_sugerida"),
        severidad=bruto.get("severidad_sugerida"),
        parametros=parametros,
        texto_original=segmento.texto,
        segmento_id_declarado=bruto.get("segmento_id"),
        segmento=segmento,
        necesita_revision_humana=bool(bruto.get("necesita_revision_humana", False)),
    )
    nivel, revisar, motivos = _confianza.calcular_confianza(señales)

    motivo_ia = bruto.get("motivo_necesita_revision")
    motivos_completos = motivos + ((motivo_ia,) if motivo_ia and bruto.get("necesita_revision_humana") else ())

    return ReglaCandidata(
        texto_original=segmento.texto,
        documento=documento.titulo,
        documento_identificador=documento.identificador,
        articulo=segmento.titulo,
        apartado=segmento.capitulo,
        version=documento.hash_texto,
        fecha=documento.fecha_publicacion or documento.fecha_disposicion,
        url_oficial=documento.url_oficial,
        organismo=documento.organismo,
        tipo=bruto.get("tipo"),
        patron=bruto.get("patron"),
        materia_sugerida=bruto.get("materia_sugerida"),
        severidad_sugerida=bruto.get("severidad_sugerida"),
        condicion_aplicacion=bruto.get("condicion_aplicacion"),
        parametros=parametros,
        excepciones=tuple(bruto.get("excepciones") or ()),
        referencias_internas=tuple(bruto.get("referencias_internas") or ()),
        explicacion_tecnica=str(bruto.get("explicacion_tecnica", "")),
        explicacion_interpretacion=str(bruto.get("explicacion_interpretacion", "")),
        nivel_confianza=nivel,
        revisar_manualmente=revisar,
        motivos_revision=motivos_completos,
        señales=señales,
    )


def extraer(
    documento: DocumentoOficial,
    *,
    tipos_segmento: Optional[Set[str]] = None,
    model: str = _interprete.MODEL,
    segmentador=_segmentador.segmentar,
) -> ResultadoExtraccion:
    """El documento oficial completo → sus candidatas, ya verificadas y con
    confianza calculada. `tipos_segmento=None` interpreta todos los
    segmentos encontrados; pasar p.ej. `{"articulo"}` se salta los anejos si
    solo interesan los artículos numerados en una corrida concreta — un
    control de coste explícito, no un filtro de contenido escondido.

    `segmentador` es inyectable (por defecto, el de XML/BOE) para que un
    documento de otra fuente reutilice interpretar→verificar→confianza sin
    duplicarlos — `segmentador_pdf.segmentar` tiene la misma firma
    (`DocumentoOficial -> List[Segmento]`) precisamente para poder pasarse
    aquí en vez de reimplementar este orquestador para PDFs."""
    segmentos = segmentador(documento)
    if tipos_segmento is not None:
        elegidos = [s for s in segmentos if s.tipo_segmento in tipos_segmento]
    else:
        elegidos = segmentos

    candidatas: List[ReglaCandidata] = []
    avisos: List[str] = []
    for segmento in elegidos:
        try:
            bruto = _interprete.interpretar(segmento, model=model)
        except ErrorDeInterpretacion as exc:
            avisos.append(str(exc))
            continue
        candidatas.append(_candidata_desde_bruto(bruto, segmento, documento))

    return ResultadoExtraccion(
        segmentos_totales=len(segmentos),
        candidatas=tuple(candidatas),
        avisos=tuple(avisos),
    )
