#!/usr/bin/env python3
"""Genera borradores de corpus normativo (`estado: BORRADOR`) a partir de las
candidatas ya extraídas en `extraccion/estado/candidatas/`.

Ver `docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md` (Prompt 1 de
la secuencia de Fase A). Decisión de producto que lo hace posible: sin
curador colegiado (Pablo, 2026-08-21) — la confianza se sustituye por
transcripción doble independiente (Prompt 2) + cita literal enlazada a la
fuente oficial, no por una firma humana.

Uso:
    python scripts/generar_borrador_corpus.py <candidatas.jsonl> [--salida DIR] [--pendientes RUTA]

Qué convierte y qué no, y por qué (deliberado, no un límite provisional):

`extraccion/modelo.py::ReglaCandidata` documenta que su `Parametro` es
"solo lo que UN artículo dice", y que construir la tabla `ejes/valores/
repliegue` de `normativa.modelo.Parametro` "exige criterio del Curador para
decidir contra qué eje de contexto se indexa, y a veces cruzar varios
artículos". Sin curador, este script no cruza esa frontera: solo convierte
candidatas donde no hace falta elegir nada —

  - UMBRAL_SIMPLE o UMBRAL_CON_EXCEPCION con EXACTAMENTE un parámetro citado
    y una cifra reconocible → una tabla de un valor, sin ejes de contexto.
  - PRESENCIA_OBLIGATORIA sin parámetro → una regla sin tabla.

Todo lo demás (varios parámetros bajo el mismo artículo, patrón ausente,
materia ausente o incoherente con el documento, sin cifra reconocible, sin
ficha de fuente oficial verificada) se descarta a pendientes-de-humano con
el motivo exacto. No se inventa.

TODA regla generada lleva `estado: BORRADOR`, y se escribe en un fichero
`_borrador_*.yaml`: el prefijo `_` es la convención ya existente de
`normativa/loader.py::descubrir()` para excluir ficheros del corpus real,
así que estas reglas son invisibles al motor de resolución además de
llevar el estado. `normativa/resolucion.py::_paso1_candidatas` descarta
además cualquier regla `BORRADOR` explícitamente, por si algún día un
fichero pierde el prefijo: dos guardarraíles independientes, no uno.

--- Descomposición de candidatas compuestas (Pablo, 2026-08-21) ---------------

Ver `docs/prd/2026-08-21-descomposicion-de-candidatas-compuestas.md`. Antes
de clasificar, cada candidata con más de un `parametro` pasa por un paso de
descomposición que intenta partirla en sub-candidatas atómicas — una por
cláusula del texto, nunca por marcador de enumeración en sí.

**Por qué por cláusula y no por letra a)/b)/c):** DB-SUA 1.2 lo demuestra con
datos reales, no con hipótesis. Su item «b)» dice «Los desniveles que no
excedan de 5 cm se resolverán con una pendiente que no exceda del 25 %» — es
UNA exigencia condicional con dos cifras, no dos exigencias independientes.
Partir por letra las trataría como atómicas y mentiría sobre la estructura
real del artículo. Por eso se agrupa por solape/posición de cada
`contexto_citado` dentro del texto (delimitado por punto, dos puntos, punto y
coma, o el inicio de un marcador de enumeración) y solo se declara atómico un
grupo de EXACTAMENTE un parámetro, sin lenguaje de remisión en su cláusula.
Todo grupo de dos o más parámetros en la misma cláusula, o con remisión
("apartado X", "conforme a", "según", "anejo"...), sigue yendo a
pendientes-de-humano — más pequeño y mejor acotado que el artículo entero,
pero sin inventar una frontera que el texto no sostiene.

Cada sub-candidata generada lleva `candidata_padre` (el `articulo` de origen)
y `criterio_particion` (qué regla de las de arriba la produjo), para
trazabilidad bidireccional. La cita literal (`norma.literal`) sigue siendo
siempre el `texto_original` COMPLETO del padre — la atomización es de la
exigencia, nunca del texto fuente.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen, confianza  # noqa: E402
from extraccion.modelo import Señales  # noqa: E402
from normativa import catalogos  # noqa: E402
from normativa.modelo import PATRONES, PRIORIDADES, TIPOS_REGLA  # noqa: E402
from normativa.validacion import validar_fichero  # noqa: E402

# ---------------------------------------------------------------------------
# Fuentes oficiales conocidas.
#
# `extraccion/interprete.py` no captura boletín ni identificador oficial del
# Real Decreto que aprueba cada Documento Básico — solo título/URL del PDF
# consolidado. Sin esos dos datos, `regla.schema.json` no permite construir
# una `NormaFuente` citable (validación 1b de `normativa/validacion.py`).
#
# Esta tabla es la ÚNICA cita añadida a mano por este script, no extraída de
# ninguna candidata: cada entrada debe verificarse contra el BOE antes de
# confiarse del todo, y el YAML generado lo dice en su cabecera. Es
# información pública y estable (qué RD aprobó qué DB), no una cifra técnica
# inventada — pero sigue sin proceder del pipeline de extracción, así que no
# se presenta como tal.
# ---------------------------------------------------------------------------
FUENTES_OFICIALES_CONOCIDAS: dict = {
    "DB-SUA": {
        "rango": "Real Decreto",
        "organismo": "Ministerio de Vivienda",
        "identificador_oficial": "RD 173/2010",
        "titulo": (
            "Real Decreto 173/2010, de 19 de febrero, por el que se modifica "
            "el Código Técnico de la Edificación, aprobado por el Real "
            "Decreto 314/2006, de 17 de marzo, en materia de accesibilidad y "
            "no discriminación de las personas con discapacidad"
        ),
        "boletin": "BOE-A-2010-3811",
        "url_oficial": "https://www.boe.es/eli/es/rd/2010/02/19/173/con",
        "prefijo_concepto": "es.rd_173_2010",
    },
}

PATRONES_UN_PARAMETRO = {"UMBRAL_SIMPLE", "UMBRAL_CON_EXCEPCION"}


# --- Utilidades ---------------------------------------------------------

def _slug(texto: str) -> str:
    s = (texto or "").lower()
    s = (
        s.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "regla"


def _numero(valor_citado: str) -> Optional[float]:
    """Primera cifra reconocible de un valor citado como "20 cm" o "más de
    6 m" o "0,85 m". No infiere unidades ni normaliza: solo el número, tal
    como aparece. Si no hay cifra, devuelve None — la candidata se
    descarta, nunca se inventa el valor."""
    m = re.search(r"(\d+(?:[.,]\d+)?)", valor_citado or "")
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _apartado_numerico(articulo: str) -> Optional[str]:
    m = re.search(r"(\d+(?:\.\d+)*)", articulo or "")
    return m.group(1) if m else None


def _nombre_corto(articulo: str) -> str:
    return re.sub(r"^DB-\w+\s+[\d.]+\s*", "", articulo or "").strip() or (articulo or "regla")


def _señales_desde_dict(d: dict) -> Señales:
    return Señales(**d)


# --- Descomposición de candidatas compuestas -------------------------------
# Ver docs/prd/2026-08-21-descomposicion-de-candidatas-compuestas.md y el
# docstring del módulo. Todo lo de esta sección opera sobre TEXTO NORMALIZADO
# (espacios colapsados) — nunca corrige guionizado ni ortografía: una cita
# que no se ancla así de simple, no se ancla, y va a pendientes.

_RE_LIMITE_FIN_CLAUSULA = re.compile(r"[.:;]\s+")
_RE_LIMITE_ENUMERACION = re.compile(r"(?:(?<=\s)|^)[a-z]\)\s")
_RE_REMISION = re.compile(
    r"\bapartado\s+\d|\bsecci[oó]n\s+SUA|\banejo\b|\bseg[uú]n\s|\bconforme\s+a\b|"
    r"\blo\s+(?:dispuesto|establecido|especificado|indicado)\s+en\b|\bp[aá]rrafo\s+\d",
    re.IGNORECASE,
)
# Palabras que, justo antes de un número, lo delatan como referencia (a una
# figura, tabla, apartado...) y no como cifra de diseño — «véase figura 2.1»
# no es un umbral. `_contar_cifras_de_umbral` las descarta.
_RE_PALABRA_REFERENCIA = re.compile(
    r"\b(?:figuras?|fig|tablas?|anejo|ap[eé]ndice|apartado|secci[oó]n|"
    r"art[ií]culo|punto|p[aá]rrafo)\.?\s*$",
    re.IGNORECASE,
)


def _normalizar_espacios(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _limites_clausula(texto_normalizado: str) -> list[int]:
    """Posiciones que delimitan cláusulas dentro del texto normalizado: tras
    «.», «:» o «;» seguidos de espacio, o al empezar un marcador de
    enumeración «a) », «b) »… Deliberadamente grueso — no es un parser
    gramatical — porque el objetivo es agrupar de más antes que partir una
    condición entrelazada (ver DB-SUA 1.2-b) en el docstring del módulo)."""
    posiciones = {0, len(texto_normalizado)}
    for m in _RE_LIMITE_FIN_CLAUSULA.finditer(texto_normalizado):
        posiciones.add(m.end())
    for m in _RE_LIMITE_ENUMERACION.finditer(texto_normalizado):
        posiciones.add(m.start())
    return sorted(posiciones)


def _clausula_de(pos: int, limites: list[int]) -> tuple[int, int]:
    for i in range(len(limites) - 1):
        if limites[i] <= pos < limites[i + 1]:
            return limites[i], limites[i + 1]
    return limites[-2], limites[-1]


def _localizar(contexto: str, texto_normalizado: str) -> Optional[int]:
    """Posición de inicio de `contexto` (normalizado) dentro de
    `texto_normalizado`, o `None` si no se puede anclar."""
    c = _normalizar_espacios(contexto)
    if not c:
        return None
    idx = texto_normalizado.find(c)
    return idx if idx >= 0 else None


def _contar_cifras_de_umbral(texto: str) -> int:
    """Cuenta menciones numéricas que parecen cifras de diseño en `texto` —
    no referencias («figura 2.1», «apartado 3») ni notas al pie «(1)».

    Señal barata, no infalible: es lo que detectó que DB-SUA 7.3 cita
    «capacidad mayor que 200 vehículos O superficie mayor que 5000 m2» como
    disyunción, pero solo `capacidad_aparcamiento` se pudo anclar en el
    texto (el otro cae a «superficie m ayor», guionizado del PDF) — sin
    esta cuenta, `capacidad` se habría convertido sola, como si el umbral
    fuera incondicional, cuando en realidad es la mitad de un «o». Si la
    cláusula de una sub-candidata de un único `parametro` no da
    exactamente 1, puede haber otra cifra de la que no hay constancia
    estructurada — no se convierte sola sin poder comprobar que lo está.

    También descarta los marcadores de artículo/apartado numerado propios
    del CTE («5 Limpieza de los acristalamientos...», «1 Excepto en
    zonas...», «2 Cuando se dispongan...»): un entero corto sin decimales
    seguido directamente de una palabra con mayúscula. Un umbral real va
    seguido de una unidad en minúscula (m, cm, %, N, lux…) o de «como
    mínimo/máximo», nunca de una palabra capitalizada — sin este filtro,
    DB-SUA 1.5 se marcaba como sospechosa por el «5» de su propio título.

    Y descarta el dígito pegado a una unidad escrita sin superíndice
    («m2», no «m²»): «5000 m2» no son dos cifras, es una con su unidad
    escrita en ASCII — un número que empieza justo donde termina una letra,
    sin espacio de por medio, es la unidad, no una cifra nueva."""
    cifras = 0
    for m in re.finditer(r"\d+(?:[.,]\d+)?", texto):
        numero = m.group()
        antes = texto[max(0, m.start() - 20):m.start()]
        despues = texto[m.end():m.end() + 4]
        if _RE_PALABRA_REFERENCIA.search(antes):
            continue
        if m.start() > 0 and texto[m.start() - 1] == "(" and despues.startswith(")"):
            continue  # nota al pie tipo «(1)»
        if "." not in numero and "," not in numero and re.match(r"\s+[A-ZÁÉÍÓÚÑ]", despues):
            continue  # marcador de artículo/apartado, no una cifra de diseño
        if m.start() > 0 and texto[m.start() - 1].isalpha():
            continue  # pegado a una letra sin espacio: es la unidad ("m2"), no una cifra nueva
        cifras += 1
    return cifras


@dataclass
class _Grupo:
    parametros: list = field(default_factory=list)
    criterio: str = ""
    motivo_forzado: Optional[tuple] = None  # (categoria, texto) si no convierte sin más
    patron_override: Optional[str] = None  # ver _descomponer, caso "clausula_independiente"


def _descomponer(cand: dict) -> list[_Grupo]:
    """Una candidata → una o más `_Grupo`. Cada grupo con `motivo_forzado is
    None` y ≤1 parámetro es candidata a conversión atómica normal (pasa por
    `_decidir` sin cambios); el resto va a pendientes con un motivo
    específico, nunca el genérico "artículo compuesto".

    Candidatas con 0 parámetros no se tocan: no hay nada que agrupar, y es
    exactamente el comportamiento del Prompt 1 (§6 del PRD de
    descomposición) — este paso amplía el pipeline, no lo reabre. Candidatas
    con 1 parámetro sí pasan por la misma comprobación de cifras que
    cualquier grupo (ver `_contar_cifras_de_umbral`): un único `parametro`
    no garantiza que su cláusula solo tenga una cifra citada — puede haber
    otra que la extracción original no llegó a estructurar."""
    parametros = cand.get("parametros") or []
    texto_norm = _normalizar_espacios(cand.get("texto_original", ""))
    limites = _limites_clausula(texto_norm)

    if len(parametros) <= 1:
        grupo = _Grupo(parametros=list(parametros), criterio="atomica_sin_particion")
        if parametros:
            pos = _localizar(parametros[0].get("contexto_citado", ""), texto_norm)
            if pos is not None:
                ini, fin = _clausula_de(pos, limites)
                n = _contar_cifras_de_umbral(texto_norm[ini:fin])
                if n > 1:
                    extracto = texto_norm[ini:fin][:160]
                    grupo.criterio = f"cifra_adicional_sospechosa:clausula[{ini}:{fin}]"
                    grupo.motivo_forzado = (
                        "posible_cifra_adicional_no_extraida",
                        f"la cláusula cita {n} cifras pero solo hay un `parametro` extraído "
                        f"(«{extracto}…»): puede haber un umbral alternativo o condicional "
                        f"del que no hay constancia estructurada — no se convierte sin poder "
                        f"comprobarlo",
                    )
        return [grupo]

    por_clausula: dict[tuple, list] = {}
    no_localizados = []
    for p in parametros:
        pos = _localizar(p.get("contexto_citado", ""), texto_norm)
        if pos is None:
            no_localizados.append(p)
            continue
        por_clausula.setdefault(_clausula_de(pos, limites), []).append(p)

    grupos: list[_Grupo] = []
    for (ini, fin), miembros in sorted(por_clausula.items()):
        texto_clausula = texto_norm[ini:fin]
        extracto = texto_clausula[:160] + ("…" if len(texto_clausula) > 160 else "")
        if _RE_REMISION.search(texto_clausula):
            grupos.append(_Grupo(
                parametros=miembros,
                criterio=f"remision_detectada:clausula[{ini}:{fin}]",
                motivo_forzado=(
                    "remision_a_otro_apartado",
                    f"la cláusula remite a otro apartado/anejo/sección para completar la exigencia "
                    f"(«{extracto}»): no se resuelve sin ese contenido, no se infiere",
                ),
            ))
        elif len(miembros) == 1 and _contar_cifras_de_umbral(texto_clausula) > 1:
            # Solo un `parametro` se ancló en esta cláusula, pero la
            # cláusula cita más de una cifra: puede ser una disyunción
            # («capacidad > 200 O superficie > 5000») donde la otra mitad
            # no se pudo anclar (DB-SUA 7.3 es exactamente este caso — ver
            # docstring de `_contar_cifras_de_umbral`). Convertir la que sí
            # se ancló como si fuera incondicional mentiría sobre la
            # estructura real, igual que partir por letra.
            grupos.append(_Grupo(
                parametros=miembros,
                criterio=f"cifra_adicional_sospechosa:clausula[{ini}:{fin}]",
                motivo_forzado=(
                    "posible_cifra_adicional_no_extraida",
                    f"la cláusula cita más de una cifra pero solo se ancló un `parametro` "
                    f"(«{extracto}»): puede haber un umbral alternativo o condicional (p. ej. "
                    f"una disyunción) del que no hay constancia estructurada — no se convierte "
                    f"sola sin poder comprobarlo",
                ),
            ))
        elif len(miembros) == 1:
            # Sub-candidata atómica genuina: desde SU punto de vista es un
            # umbral simple, aunque el artículo padre estuviera clasificado
            # COMBINACION_LOGICA/AGREGACION_AMBITO (una etiqueta sobre el
            # conjunto, no sobre esta cláusula sola). Sin este override,
            # `_decidir` no reconoce el patrón del padre como de un solo
            # parámetro y la descarta con el motivo genérico que este PRD
            # existe para eliminar — ver
            # docs/prd/2026-08-21-descomposicion-de-candidatas-compuestas.md §5.
            grupos.append(_Grupo(
                parametros=miembros,
                criterio=f"clausula_independiente:clausula[{ini}:{fin}]",
                patron_override="UMBRAL_SIMPLE",
            ))
        else:
            grupos.append(_Grupo(
                parametros=miembros,
                criterio=f"grupo_no_atomico:clausula[{ini}:{fin}]",
                motivo_forzado=(
                    "condicion_compuesta_no_atomica",
                    f"{len(miembros)} cifras citadas en la misma cláusula del texto — pueden estar "
                    f"condicionadas entre sí («{extracto}»); no se separan sin ese criterio (ver "
                    f"docs/prd/2026-08-21-descomposicion-de-candidatas-compuestas.md §5)",
                ),
            ))

    if no_localizados:
        grupos.append(_Grupo(
            parametros=no_localizados,
            criterio="contexto_no_localizable",
            motivo_forzado=(
                "contexto_no_localizable",
                f"{len(no_localizados)} parámetro(s) cuyo contexto_citado no se pudo anclar, tras "
                f"normalizar espacios, dentro de texto_original — probable artefacto de extracción "
                f"del PDF (guionizado, tablas reformateadas); no se adivina su posición",
            ),
        ))

    return grupos


def _unidades(cand: dict) -> list[dict]:
    """Las sub-candidatas de una candidata, con trazabilidad al padre. Cada
    unidad es una copia superficial de `cand` con `parametros` recortado al
    grupo y dos campos nuevos: `candidata_padre` y `criterio_particion`."""
    unidades = []
    for g in _descomponer(cand):
        unidad = dict(cand)
        unidad["parametros"] = g.parametros
        unidad["candidata_padre"] = cand.get("articulo")
        unidad["criterio_particion"] = g.criterio
        unidad["_motivo_forzado"] = g.motivo_forzado
        if g.patron_override:
            unidad["patron"] = g.patron_override
        unidades.append(unidad)
    return unidades


# --- Clasificación --------------------------------------------------------

def _decidir(cand: dict) -> Optional[tuple[str, str]]:
    """`(categoria, motivo)` de descarte, o `None` si la candidata se puede
    convertir. Cada vía de conversión está permitida explícitamente; nunca
    se convierte por eliminación."""
    doc_id = cand.get("documento_identificador")
    materia = cand.get("materia_sugerida")
    tipo = cand.get("tipo")
    patron = cand.get("patron")
    parametros = cand.get("parametros") or []

    if doc_id not in FUENTES_OFICIALES_CONOCIDAS:
        return (
            "sin_fuente_oficial_verificada",
            f"sin ficha de fuente oficial verificada para «{doc_id}»: no se inventa la cita de la norma",
        )

    catalogo_materias = catalogos.materias()
    if not materia or materia not in catalogo_materias:
        return (
            "materia_ausente_o_fuera_de_catalogo",
            f"materia sugerida «{materia}» ausente o fuera del catálogo cerrado",
        )

    permitidos = catalogo_materias[materia].get("documentos_basicos") or []
    if doc_id not in permitidos:
        return (
            "materia_incoherente_con_documento",
            f"la materia «{materia}» no se regula en «{doc_id}» según el catálogo "
            f"(la regula {permitidos or 'ningún Documento Básico'}) — incoherencia materia/documento",
        )

    if not patron or patron not in PATRONES:
        return (
            "sin_patron_evaluable",
            f"sin patrón evaluable asignado por la extracción (patron={patron!r})",
        )

    if tipo not in TIPOS_REGLA or not TIPOS_REGLA[tipo]:
        return (
            "tipo_no_evaluable",
            f"tipo «{tipo}» no es evaluable: no aporta una exigencia comprobable",
        )

    if patron == "PRESENCIA_OBLIGATORIA" and not parametros:
        return None  # convertible, sin tabla de parámetro

    if patron in PATRONES_UN_PARAMETRO and len(parametros) == 1:
        if _numero(parametros[0].get("valor_citado", "")) is None:
            return (
                "valor_no_parseable",
                f"el valor citado «{parametros[0].get('valor_citado')}» no contiene una "
                f"cifra reconocible: no se tabula sin inventar el número",
            )
        return None  # convertible

    if len(parametros) == 0:
        return (
            "sin_parametros_extraidos",
            "sin parámetros extraídos: el artículo no cita cifras verificables o remite a otra sección",
        )

    return (
        "multiples_exigencias_agrupadas",
        f"el artículo agrupa {len(parametros)} exigencias distintas bajo un único segmento: "
        f"descomponerlo en reglas separadas exige criterio del Curador, no se auto-divide "
        f"(ver extraccion/modelo.py::ReglaCandidata, docstring de Parametro)",
    )


# --- Construcción de la regla ---------------------------------------------

def _construir_documento(cand: dict, nivel_confianza: str, sufijo_desambiguador: Optional[str] = None,
                         estado: str = "BORRADOR", documento_sha256: Optional[str] = None) -> dict:
    """`sufijo_desambiguador` solo se pasa cuando la descomposición produjo
    más de una sub-candidata atómica del mismo artículo padre (p. ej. DB-SUA
    1.2 da 3 conversiones limpias) — sin él, las tres competirían por el
    mismo `concept_id` derivado solo del artículo. Con una única conversión
    por artículo (el caso del Prompt 1: DB-SUA 2.2, 5.1, 7.1) el `concept_id`
    no cambia — la trazabilidad ya asentada no se rompe por este paso nuevo.

    `estado`/`documento_sha256` son del Prompt 2
    (docs/prd/2026-08-21-verificacion-doble-del-corpus.md): por defecto
    siguen produciendo exactamente el `BORRADOR` de siempre —
    `scripts/verificar_doble_ruta.py` es el único llamante que pasa
    `estado="VERIFICADA_AUTOMATICA"` con su hash."""
    doc_id = cand["documento_identificador"]
    fuente = FUENTES_OFICIALES_CONOCIDAS[doc_id]
    materia = cand["materia_sugerida"]
    parametros = cand.get("parametros") or []
    nombre_corto = _nombre_corto(cand.get("articulo", ""))
    apartado_num = _apartado_numerico(cand.get("articulo", "")) or "0"
    base_slug = _slug(nombre_corto)
    if sufijo_desambiguador:
        base_slug = f"{base_slug}_{_slug(sufijo_desambiguador)}"
    slug = f"{apartado_num.replace('.', '_')}_{base_slug}"
    prefijo = fuente["prefijo_concepto"]

    concept_id = f"{prefijo}.{materia}.{slug}"
    instance_id = f"{concept_id}@1"

    if parametros:
        p = parametros[0]
        valor = _numero(p["valor_citado"])
        parametro = {
            "ejes": [],
            "unidad": p.get("unidad"),
            "repliegue": ["todos"],
            "valores": [{"valor": valor}],
        }
        mensaje = p.get("contexto_citado") or nombre_corto
    else:
        parametro = None
        mensaje = cand.get("condicion_aplicacion") or nombre_corto

    prioridad = cand.get("severidad_sugerida")
    if prioridad not in PRIORIDADES:
        prioridad = "recomendable"

    fecha = cand.get("fecha") or "1900-01-01"

    nombre = nombre_corto if not sufijo_desambiguador else f"{nombre_corto} — {sufijo_desambiguador.replace('_', ' ')}"

    etiqueta_procedencia = "borrador_automatico" if estado == "BORRADOR" else "verificado_doble_ruta"

    regla = {
        "concept_id": concept_id,
        "instance_id": instance_id,
        "nombre": nombre[:200],
        "materia": materia,
        "tipo": cand["tipo"],
        "prioridad": prioridad,
        "nivel_de_conocimiento": 2,  # normativa verificable (regla.schema.json §comentario)
        "estado": estado,
        "aplicabilidad": {"ambito": "es"},
        "patron": cand["patron"],
        "parametro": parametro,
        "condiciones": None,
        "mensaje": mensaje,
        "explicacion_tecnica": cand.get("explicacion_tecnica") or "",
        "explicacion_cliente": cand.get("condicion_aplicacion") or "",
        "tags": [
            etiqueta_procedencia,
            _slug(doc_id),
            materia,
            f"confianza_{nivel_confianza.lower()}",
        ],
        "vigencia": {"vigencia_desde": fecha},
    }

    fuente_norma = {k: v for k, v in fuente.items() if k != "prefijo_concepto"}
    if documento_sha256:
        fuente_norma["documento_sha256"] = documento_sha256

    norma = {
        "concept_id": f"{prefijo}.{_slug(doc_id)}.norma",
        "instance_id": f"{prefijo}.{_slug(doc_id)}.norma@1",
        "ambito": "es",
        "fuente": fuente_norma,
        "articulo": {
            "documento_basico": doc_id,
            "seccion": cand.get("apartado"),
            "apartado": apartado_num,
            "tabla": None,
        },
        "literal": cand.get("texto_original", ""),
        "vigencia": {"vigencia_desde": fecha},
    }

    return {"version": 1, "norma": norma, "reglas": [regla]}


def _cabecera(cand: dict, nivel_confianza: str, revisar: bool, motivos) -> str:
    lineas = [
        "# Generado automáticamente por scripts/generar_borrador_corpus.py — NO EDITAR A MANO.",
        f"# Origen: {cand.get('documento_identificador')} — {cand.get('articulo')}",
        f"# Candidata: extraccion/estado/candidatas/ (version={cand.get('version', '')[:16]}…)",
        "#",
        "# ESTADO: BORRADOR. Una sola ruta de extracción, sin verificar. El motor",
        "# de resolución nunca la usa para afirmar cumplimiento (ver",
        "# normativa/resolucion.py::_paso1_candidatas). Promoción a",
        "# VERIFICADA_AUTOMATICA es tarea del Prompt 2 (transcripción doble).",
        "#",
        f"# Confianza de la extracción: {nivel_confianza} "
        f"({'revisar manualmente' if revisar else 'sin aviso de revisión'}).",
    ]
    criterio = cand.get("criterio_particion")
    if criterio and criterio != "atomica_sin_particion":
        lineas.append("#")
        lineas.append(
            f"# Sub-candidata por descomposición del artículo padre «{cand.get('candidata_padre')}» "
            f"(criterio: {criterio}). Ver docs/prd/2026-08-21-descomposicion-de-candidatas-compuestas.md."
        )
    lineas += [
        "#",
        "# vigencia_desde es la fecha de la versión del PDF consolidado que",
        "# descargó extraccion/ (campo «fecha» de la candidata), NO una fecha de",
        "# entrada en vigor verificada del Real Decreto — puede haber una",
        "# consolidación posterior a 2010. Confirmar contra el BOE antes de usarla",
        "# para resolver vigencia legal.",
    ]
    if motivos:
        lineas.append("# Motivos de revisión señalados por la propia extracción:")
        lineas.extend(
            f"#   {linea}"
            for m in motivos
            for linea in ((m or "").splitlines() or [""])
        )
    lineas.append(
        "#\n# La cita de la fuente oficial (boletín, identificador) la añade este\n"
        "# script a mano desde una tabla propia — no la extrae el pipeline de\n"
        "# extraccion/. Verificar contra el BOE antes de promover esta regla."
    )
    return "\n".join(lineas) + "\n\n"


# --- Orquestación -----------------------------------------------------------

def procesar(ruta_candidatas: Path, salida_dir: Path, pendientes_ruta: Path) -> dict:
    candidatas = almacen.leer(ruta_candidatas)
    if not candidatas:
        raise SystemExit(f"«{ruta_candidatas}» no contiene candidatas (fichero vacío o inexistente)")

    salida_dir.mkdir(parents=True, exist_ok=True)
    pendientes_ruta.parent.mkdir(parents=True, exist_ok=True)

    prefijo_stem = f"_borrador_{_slug(ruta_candidatas.stem.split('__')[1] if '__' in ruta_candidatas.stem else ruta_candidatas.stem)}"
    # Limpieza idempotente: solo los ficheros que este mismo origen generó.
    for viejo in salida_dir.glob(f"{prefijo_stem}_*.yaml"):
        viejo.unlink()

    convertidas: list[Path] = []
    descartadas: list[dict] = []
    motivos_por_categoria: Counter = Counter()
    concept_ids_vistos: set[str] = set()
    total_unidades = 0

    for cand in candidatas:
        unidades = _unidades(cand)
        total_unidades += len(unidades)
        # Sufijo desambiguador solo si la descomposición produjo más de una
        # sub-candidata atómica del mismo padre — si es una sola (el caso ya
        # existente del Prompt 1), el concept_id no cambia. Ver docstring de
        # _construir_documento.
        atomicas_del_padre = sum(1 for u in unidades if u["_motivo_forzado"] is None)

        for unidad in unidades:
            motivo_forzado = unidad.pop("_motivo_forzado")
            motivo = motivo_forzado or _decidir(unidad)
            if motivo is not None:
                categoria, texto = motivo
                motivos_por_categoria[categoria] += 1
                descartadas.append({**unidad, "motivo_descarte": texto, "categoria_descarte": categoria})
                continue

            señales = _señales_desde_dict(unidad["señales"])
            nivel_confianza, revisar, motivos_conf = confianza.calcular_confianza(señales)

            sufijo = None
            if atomicas_del_padre > 1 and unidad["parametros"]:
                sufijo = unidad["parametros"][0]["nombre"]

            doc = _construir_documento(unidad, nivel_confianza, sufijo_desambiguador=sufijo)
            regla = doc["reglas"][0]

            if regla["concept_id"] in concept_ids_vistos:
                motivos_por_categoria["concept_id_duplicado"] += 1
                descartadas.append({
                    **unidad,
                    "motivo_descarte": f"concept_id «{regla['concept_id']}» ya generado por otra candidata de esta misma corrida",
                    "categoria_descarte": "concept_id_duplicado",
                })
                continue

            fallos_esquema = validar_fichero(doc)
            if fallos_esquema:
                motivos_por_categoria["invalida_contra_esquema"] += 1
                descartadas.append({
                    **unidad,
                    "motivo_descarte": "regla construida pero no pasa el esquema: " + "; ".join(fallos_esquema),
                    "categoria_descarte": "invalida_contra_esquema",
                })
                continue

            concept_ids_vistos.add(regla["concept_id"])
            nombre_fichero = f"{prefijo_stem}_{regla['concept_id'].split('.')[-1]}.yaml"
            destino = salida_dir / nombre_fichero
            cabecera = _cabecera(unidad, nivel_confianza, revisar, motivos_conf)
            with destino.open("w", encoding="utf-8") as f:
                f.write(cabecera)
                yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            convertidas.append(destino)

    with pendientes_ruta.open("w", encoding="utf-8") as f:
        import json
        for d in descartadas:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    return {
        "leidas": len(candidatas),
        "unidades": total_unidades,
        "convertidas": convertidas,
        "descartadas": len(descartadas),
        "motivos": motivos_por_categoria,
        "pendientes_ruta": pendientes_ruta,
    }


def _informe(resultado: dict) -> str:
    lineas = [
        f"Candidatas leídas:      {resultado['leidas']}",
        f"Sub-candidatas (tras descomposición): {resultado['unidades']}",
        f"Convertidas a BORRADOR: {len(resultado['convertidas'])}",
        f"Descartadas a pendientes: {resultado['descartadas']}",
    ]
    if resultado["convertidas"]:
        lineas.append("\nFicheros generados:")
        lineas.extend(f"  - {p.relative_to(RAIZ)}" for p in resultado["convertidas"])
    if resultado["motivos"]:
        lineas.append("\nMotivos de descarte:")
        for categoria, n in sorted(resultado["motivos"].items(), key=lambda kv: -kv[1]):
            lineas.append(f"  - {categoria}: {n}")
    lineas.append(f"\nPendientes de humano: {resultado['pendientes_ruta'].relative_to(RAIZ)}")
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("candidatas", type=Path, help="Ruta al .jsonl de candidatas (extraccion/estado/candidatas/...)")
    parser.add_argument(
        "--salida", type=Path, default=RAIZ / "normativa" / "es" / "estatal",
        help="Directorio donde escribir los ficheros _borrador_*.yaml (default: normativa/es/estatal/)",
    )
    parser.add_argument(
        "--pendientes", type=Path, default=None,
        help="Ruta del .jsonl de pendientes-de-humano (default: extraccion/estado/pendientes/<stem>.pendientes.jsonl)",
    )
    args = parser.parse_args()

    ruta_candidatas = args.candidatas if args.candidatas.is_absolute() else RAIZ / args.candidatas
    pendientes_ruta = args.pendientes or (RAIZ / "extraccion" / "estado" / "pendientes" / f"{ruta_candidatas.stem}.pendientes.jsonl")

    resultado = procesar(ruta_candidatas, args.salida, pendientes_ruta)
    print(_informe(resultado))


if __name__ == "__main__":
    main()
