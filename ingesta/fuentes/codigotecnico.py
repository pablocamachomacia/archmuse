"""Conector contra el portal oficial del CTE (`codigotecnico.org`), gestionado
por el Ministerio de Transportes, Movilidad y Agenda Urbana.

**Por qué esta fuente y no el "código electrónico" del BOE**: el BOE publica
una compilación consolidada del CTE, pero es UN ÚNICO PDF de más de 1300
páginas que mezcla el CTE con otras ~100 normas no relacionadas (prevención
de riesgos laborales, etc.) — verificado descargándolo entero, no asumido.
`codigotecnico.org` en cambio publica cada Documento Básico como su propio
PDF, con URL estable y `Last-Modified` propio — encaja con "un documento
por DB, versionable por separado" mucho mejor que el bundle del BOE.
Decisión documentada en la memoria de sesión, no solo aquí.

**Catálogo cerrado, no descubierto**: a diferencia del BOE (que lista lo
publicado cada día), esta fuente no tiene un "sumario" real — es un puñado
fijo de documentos que el Ministerio actualiza in situ. `_CATALOGO` es esa
lista, verificada contra las páginas reales de cada DB en codigotecnico.org
(no adivinada). Añadir un DB nuevo es añadir una entrada aquí, no escribir
lógica nueva.

**DB-SE tiene 6 documentos, no 1**: el Documento Básico de Seguridad
Estructural se publica partido por material/materia (SE general + SE-AE
acciones en la edificación, SE-C cimientos, SE-A acero, SE-F fábrica, SE-M
madera) — estructura real del CTE, no una decisión de este conector.

**Doble fuente, nunca fusionada aquí** — condición de Pablo al aprobar
`docs/design/2026-08-06-auditoria-fuentes-cte.md`: este conector trae el
*contenido* (el PDF ya consolidado por el Ministerio); `boe_identificadores`
en `_CATALOGO` declara qué instrumento(s) del BOE constituyen ese contenido,
para trazabilidad legal si `codigotecnico.org` cambiara o desapareciera.
Son datos **curados a mano**, verificados contra el BOE real en la sesión
de la auditoría (búsqueda de cada Real Decreto/Orden + comprobación cruzada
de que la fecha impresa en la portada del PDF coincide con la fecha del
instrumento) — NUNCA reconstruidos ni inferidos en tiempo de ejecución, eso
sería el motor de consolidación legal que el diseño aprobado descarta
explícitamente. Dos son de confianza media, declarada así en el propio
dato, no escondida:
- El alcance exacto de la Orden VIV/984/2009 no se verificó DB por DB (las
  fuentes consultadas dicen "determinados documentos básicos" sin
  desglosar) — se incluye en SE/SUA porque son los DB más plausibles según
  el contenido de esa orden (acristalamiento, aperturas), no confirmado.
- DB-SE-C/F/M no se diferenciaron de DB-SE a efectos de qué instrumentos
  los tocan exactamente — se les asigna la misma cadena que DB-SE.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import List, Tuple

from .. import red
from ..errores import DocumentoIlegible
from ..modelo import DocumentoOficial, ItemSumario
from .base import FuenteOficial

ORGANISMO = "Ministerio de Transportes, Movilidad y Agenda Urbana"

# Instrumentos BOE reales, verificados en la sesión de auditoría (no
# adivinados) — identificador -> (rango, fecha, qué toca, en qué DB se cita).
# RD 314/2006 (BOE-A-2006-5515): aprueba el CTE original — base de todos
#   los DB salvo DB-HR (que no existía todavía en 2006).
# RD 1371/2007 (BOE-A-2007-18400): aprueba DB-HR por primera vez.
# Orden VIV/984/2009 (BOE-A-2009-6743): "modifica determinados documentos
#   básicos" — alcance exacto no desglosado en las fuentes consultadas.
# RD 732/2019 (BOE-A-2019-18528): sustituye DB-HE entero, nueva HS6 (radón),
#   modifica DB-SI (propagación exterior), actualiza referencias en casi
#   todos los DB — EXCEPTO DB-SE-AE y DB-SE-A, excluidos explícitamente.
#   Confirmado por fecha de portada "20 diciembre 2019" en DB-SE y DB-HR.
# RD 450/2022 (BOE-A-2022-9848): nueva HE6 (recarga de vehículo eléctrico).
#   Confirmado por fecha de portada "14 junio 2022" en DB-HE, DB-HS, DB-SUA
#   simultáneamente — los 3 lo reflejan como su última modificación.
# RD 164/2025 (BOE-A-2025-7190): DB-SI, coordinación con el Reglamento de
#   seguridad contra incendios en establecimientos industriales. Confirmado
#   por fecha de portada "4 marzo 2025" en DB-SI (la propia fecha del RD).
_RD_314_2006 = "BOE-A-2006-5515"
_RD_1371_2007 = "BOE-A-2007-18400"
_ORDEN_VIV_984_2009 = "BOE-A-2009-6743"
_RD_732_2019 = "BOE-A-2019-18528"
_RD_450_2022 = "BOE-A-2022-9848"
_RD_164_2025 = "BOE-A-2025-7190"


@dataclass(frozen=True)
class _EntradaCatalogo:
    identificador: str  # "DB-SI", "DB-SE-AE"...
    titulo: str
    url: str
    # Fecha impresa en la portada del PDF (verificada por regex contra el
    # documento real, no inventada) — refleja SOLO la última modificación,
    # no el historial completo; para eso está `boe_identificadores`.
    fecha_publicacion: str
    boe_identificadores: Tuple[str, ...] = field(default_factory=tuple)


_CATALOGO: tuple[_EntradaCatalogo, ...] = (
    _EntradaCatalogo("DB-SE", "Documento Básico SE — Seguridad Estructural", "https://www.codigotecnico.org/pdf/Documentos/SE/DBSE.pdf", "2019-12-20", (_RD_314_2006, _ORDEN_VIV_984_2009, _RD_732_2019)),
    _EntradaCatalogo("DB-SE-AE", "Documento Básico SE-AE — Acciones en la Edificación", "https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-AE.pdf", "2006-03-17", (_RD_314_2006,)),  # excluido explícitamente de RD 732/2019
    _EntradaCatalogo("DB-SE-C", "Documento Básico SE-C — Cimientos", "https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-C.pdf", "2019-12-20", (_RD_314_2006, _ORDEN_VIV_984_2009, _RD_732_2019)),
    _EntradaCatalogo("DB-SE-A", "Documento Básico SE-A — Acero", "https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-A.pdf", "2006-03-17", (_RD_314_2006,)),  # excluido explícitamente de RD 732/2019
    _EntradaCatalogo("DB-SE-F", "Documento Básico SE-F — Fábrica", "https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-F.pdf", "2019-12-20", (_RD_314_2006, _ORDEN_VIV_984_2009, _RD_732_2019)),
    _EntradaCatalogo("DB-SE-M", "Documento Básico SE-M — Madera", "https://www.codigotecnico.org/pdf/Documentos/SE/DBSE-M.pdf", "2019-12-20", (_RD_314_2006, _ORDEN_VIV_984_2009, _RD_732_2019)),
    _EntradaCatalogo("DB-SI", "Documento Básico SI — Seguridad en caso de Incendio", "https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf", "2025-03-04", (_RD_314_2006, _RD_732_2019, _RD_164_2025)),
    _EntradaCatalogo("DB-SUA", "Documento Básico SUA — Seguridad de Utilización y Accesibilidad", "https://www.codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf", "2022-06-14", (_RD_314_2006, _ORDEN_VIV_984_2009, _RD_732_2019, _RD_450_2022)),
    _EntradaCatalogo("DB-HS", "Documento Básico HS — Salubridad", "https://www.codigotecnico.org/pdf/Documentos/HS/DBHS.pdf", "2022-06-14", (_RD_314_2006, _RD_732_2019, _RD_450_2022)),
    _EntradaCatalogo("DB-HE", "Documento Básico HE — Ahorro de Energía", "https://www.codigotecnico.org/pdf/Documentos/HE/DBHE.pdf", "2022-06-14", (_RD_314_2006, _RD_732_2019, _RD_450_2022)),
    _EntradaCatalogo("DB-HR", "Documento Básico HR — Protección frente al Ruido", "https://www.codigotecnico.org/pdf/Documentos/HR/DBHR.pdf", "2019-12-20", (_RD_1371_2007, _RD_732_2019)),  # DB-HR no viene en el RD 314/2006 original
)

_POR_ID = {e.identificador: e for e in _CATALOGO}


def _texto_desde_pdf(identificador: str, crudo: bytes) -> str:
    # Import perezoso: mantiene `pypdf` fuera de todo lo que no ingiere PDFs
    # (BOE, `normativa/`, `analyzer/`) — mismo principio que evita que
    # `anthropic` se importe fuera de `ai_analyst.py`/`extraccion/interprete.py`.
    from io import BytesIO

    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        lector = PdfReader(BytesIO(crudo))
        paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    except PdfReadError as exc:
        raise DocumentoIlegible(identificador, f"PDF ilegible: {exc}") from exc

    if not any(p.strip() for p in paginas):
        raise DocumentoIlegible(identificador, "el PDF no trae texto extraíble (¿es un escaneado sin OCR?)")

    return "\f".join(paginas)  # \f (form feed) marca el salto de página — lo usa el segmentador para descartar cabeceras repetidas


class FuenteCodigoTecnico(FuenteOficial):
    id = "codigotecnico"

    def listar_sumario(self, fecha: date) -> List[ItemSumario]:
        """`fecha` se ignora deliberadamente: esta fuente no es un boletín
        diario, es un catálogo pequeño y fijo de documentos vigentes que el
        Ministerio actualiza in situ. Devuelve el catálogo completo siempre
        — lista vacía nunca ocurre aquí salvo que `_CATALOGO` esté vacío,
        así que no hace falta el mismo cuidado festivo/fin-de-semana que
        `FuenteBOE.listar_sumario`."""
        return [
            ItemSumario(
                identificador=e.identificador,
                titulo=e.titulo,
                fuente=self.id,
                fecha_publicacion=fecha.strftime("%Y%m%d"),
                seccion_codigo="",
                seccion_nombre="Código Técnico de la Edificación",
                departamento_codigo="",
                departamento_nombre=ORGANISMO,
                epigrafe=None,
                url_html=None,
                url_pdf=e.url,
                url_xml=None,
            )
            for e in _CATALOGO
        ]

    def descargar_documento(self, item: ItemSumario) -> DocumentoOficial:
        return self.descargar_por_id(item.identificador)

    def descargar_por_id(self, identificador: str) -> DocumentoOficial:
        """Descarga directa por identificador de catálogo (`"DB-SI"`...).
        Mismo patrón de extensión que `FuenteBOE.descargar_por_id` — no forma
        parte del contrato `FuenteOficial`, pero es lo que `ingerir_documento`
        usa quien conoce ya el identificador y no necesita listar nada."""
        entrada = _POR_ID.get(identificador)
        if entrada is None:
            raise DocumentoIlegible(identificador, f"no está en el catálogo de {self.id} (¿DB nuevo sin añadir a _CATALOGO?)")

        # NO se usa `Last-Modified` para nada con significado legal: los 11
        # documentos del catálogo devolvieron la misma fecha-hora (a
        # segundos de diferencia) en la sesión de auditoría — es la huella
        # de un redespliegue del sitio, no de una actualización real del
        # texto. La fecha que importa es `entrada.fecha_publicacion`
        # (impresa en la propia portada del PDF, curada en `_CATALOGO`).
        crudo, _ = red.obtener_con_cabeceras(entrada.url, accept="application/pdf")
        texto = _texto_desde_pdf(identificador, crudo)

        return DocumentoOficial(
            identificador=entrada.identificador,
            fuente=self.id,
            titulo=entrada.titulo,
            organismo=ORGANISMO,
            rango_codigo=None,
            rango_nombre="Documento Básico (texto consolidado vigente)",
            numero_oficial=None,
            fecha_publicacion=entrada.fecha_publicacion,
            fecha_disposicion=None,
            fecha_actualizacion=None,  # "última comprobación" la lleva el ledger (`EstadoDescarga.fecha_descarga`), no este campo
            url_oficial=entrada.url,
            url_xml=entrada.url,  # nombre heredado del contrato de `DocumentoOficial`; aquí es la URL del PDF, no de un XML
            texto_crudo=texto,
            hash_texto=hashlib.sha256(crudo).hexdigest(),
            formato="pdf",
            bytes_crudos=crudo,
            referencias_boe=entrada.boe_identificadores,
        )
