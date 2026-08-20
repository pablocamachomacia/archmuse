# -*- coding: utf-8 -*-
"""CAP-1 — `superficie_util_db_si`, la superficie útil tal como la define el DB-SI.

Anejo SI A del DB-SI, literal:

    Superficie útil
    Superficie en planta de un recinto, sector o edificio ocupable por las
    personas.

**Esto NO es `evaluator._superficie_suelo_agregada_m2`, y no debe sustituirla.**
Aquella suma áreas y excluye Terraza/Tendedero por el rótulo; es un criterio
propio de ArchMuse, útil para las reglas que ya lo usan y no citable como
magnitud normativa. Ésta se calcula por unión geométrica y clasifica cada
recinto contra listas de la norma. Coexisten a propósito
(`docs/design/DB-SI_DECISIONS.md` D1.b): la vieja tiene consumidores antiguos
que esta fase no toca.

---

### Cómo se calcula

1. Se clasifica cada recinto (§ *Clasificación*).
2. Si alguno no se puede clasificar, el hecho es `UNKNOWN`. No se calcula nada
   más: incluir o excluir ese recinto cambia el número materialmente y ninguna
   de las dos opciones es defendible.
3. Se valida la geometría de cada recinto (existe, es un polígono válido, tiene
   área positiva).
4. Se comprueba el solape entre recintos.
5. Se toma el **área de la unión geométrica** (`unary_union`), no la suma.

### Por qué el solape produce `UNKNOWN` y no simplemente la unión

La unión elimina el doble cómputo, pero no resuelve la ambigüedad de fondo.
Medido en `ejemplo.dxf`: en VT6/2 el polígono rotulado «Salón/cocina» (58,58 m²)
contiene a las cuatro terrazas. La unión daría un número plausible, pero no
sabemos si el salón mide realmente 58 m² o si ese polígono es un contorno
agrupador que el parser conservó y el salón real es otro. Publicar la unión
sería elegir una de las dos lecturas sin evidencia — es la opción (b) que
`DB-SI_DECISIONS.md` D3.3 descartó. El área de la unión se conserva en
`diagnostico` para que un humano la vea, nunca como valor del hecho.

### Clasificación de recintos: la definición es INCLUSIVA

La clave está en lo que el DB-SI **no** tiene: **no existe ninguna lista de
exclusiones de superficie útil**. Se buscó en el documento entero (92 páginas);
la única exclusión de superficie es *«(4) Las zonas de aseos no computan a
efectos del cálculo de la superficie **construida**»* — otra magnitud y otro
propósito (clasificar locales de riesgo especial). Para la superficie útil no
hay exclusión de ningún tipo.

Por tanto la carga de la prueba está en excluir, no en incluir: un recinto de
la vivienda es superficie útil salvo que la norma diga lo contrario, y no lo
dice de ninguno. **La terraza se incluye** (ver `DB-SI_DECISIONS.md` D6 para
la demostración completa); el tendedero también, por el mismo motivo.

Queda una única clase con tratamiento propio, y sí está citada:

- **Ocupación nula** — DB-SI, Anejo SI A: *«Zona en la que la presencia de
  personas sea ocasional o bien a efectos de mantenimiento, tales como salas de
  máquinas y cuartos de instalaciones, locales para material de limpieza,
  determinados almacenes y archivos, trasteros de viviendas»*. **Sigue siendo
  superficie útil**: el Anejo la excluye del *«número de ocupantes»*, no de la
  superficie. Se marca aparte porque CAP-3 la necesitará.

`AMBIGUO` queda sólo para lo que no se puede identificar como recinto: un
polígono **sin rótulo**. Ahí la duda no es normativa sino de lectura del plano
— podría ser un contorno agrupador, un patio o el propio perímetro de la
vivienda, y en este parser eso ocurre de verdad (es la causa del solape de
VT5/1). Un polígono anónimo no se da por ocupable.

### Confianza

`Media`, nunca `Alta`, aunque geometría y clasificación estén limpias. El techo
lo pone el emparejamiento: se clasifica por el **rótulo de texto** del plano,
que es una convención de dibujo del estudio, no una propiedad del recinto. Un
tendedero rotulado «Lavadero» se clasifica distinto sin que la geometría haya
cambiado. Elevarlo a `Alta` exigiría una taxonomía tipada de recintos en el
parser, que hoy no existe (`DB-SI_IMPLEMENTATION_PLAN.md` §4).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .hechos import KNOWN, MEDIA, UNKNOWN, Hecho, Motivo

# `concept_id` de la definición en `normativa/terminologia/dbsi_anejo_a.yaml`.
# Se guarda la referencia, no el literal: `analyzer/` no importa `normativa/`
# (ver docstring de `hechos.py`).
DEFINICION_CONCEPT_ID = "es.cte.db_si.anejo_a.superficie_util"

# Mismo orden de magnitud que `evaluator.ROOM_OVERLAP_TOLERANCE_M2` (0.05):
# por debajo de esto es ruido de dibujo, no un contorno agrupador colado.
TOLERANCIA_SOLAPE_M2 = 0.05

# Área por debajo de la cual un polígono no representa un recinto real.
AREA_MINIMA_M2 = 0.01

# --- Códigos de motivo (`DB-SI_FACT_MODEL.md` §8) --------------------------

SIN_RECINTOS = "NO_ROOMS"
GEOMETRIA_AUSENTE = "GEOMETRY_MISSING"
GEOMETRIA_INVALIDA = "GEOMETRY_INVALID"
SOLAPE_NO_RESUELTO = "GEOMETRY_OVERLAP_UNRESOLVED"
RECINTO_AMBIGUO = "ROOM_CLASSIFICATION_AMBIGUOUS"

# --- Clasificación de recintos ---------------------------------------------

OCUPABLE = "ocupable"
OCUPACION_NULA = "ocupacion_nula"
AMBIGUO = "ambiguo"

# DB-SI, Anejo SI A, «Zona de ocupación nula». Es la ÚNICA lista cerrada del
# módulo, y existe porque la norma la enumera. No hay lista de «ocupables»:
# la definición de superficie útil es inclusiva y no admite exclusiones.
_OCUPACION_NULA = re.compile(
    r"TRASTERO|SALA DE MAQUINAS|CUARTO DE INSTALACIONES|CUARTO DE LIMPIEZA|"
    r"ARCHIVO|ALMACEN"
)


def _normalizar(etiqueta: str) -> str:
    """Mayúsculas y sin acentos. Misma convención que `evaluator._normalize`,
    reimplementada aquí para que este módulo no dependa del evaluador — es la
    base de CAP-2/CAP-3 y no debe heredar su ciclo de vida."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", etiqueta)
        if unicodedata.category(c) != "Mn"
    )
    return sin_tildes.upper().strip()


def clasificar_recinto(etiqueta: Optional[str]) -> str:
    """`OCUPABLE`, `OCUPACION_NULA` o `AMBIGUO` para un rótulo de recinto.

    **Por defecto, ocupable.** El DB-SI no excluye ningún recinto de la
    superficie útil, así que un recinto rotulado de la vivienda lo es —
    terraza y tendedero incluidos. Sólo se aparta lo que el Anejo SI A
    enumera como zona de ocupación nula, y ni siquiera eso deja de ser
    superficie útil: se marca para que CAP-3 pueda descontarlo del número de
    ocupantes, que es lo único que la norma excluye.

    Un recinto **sin rótulo** es `AMBIGUO`: ahí no se está juzgando si es
    ocupable, sino si es un recinto. Un polígono anónimo puede ser el contorno
    agrupador de la vivienda, y en este parser eso ocurre. La ausencia de
    etiqueta no es evidencia de nada (`INFERENCE_ENGINE.md` §2.2).
    """
    if not etiqueta or not etiqueta.strip():
        return AMBIGUO
    if _OCUPACION_NULA.search(_normalizar(etiqueta)):
        return OCUPACION_NULA
    return OCUPABLE


@dataclass(frozen=True)
class _RecintoRevisado:
    etiqueta: str
    clase: str
    poligono: Optional[Polygon]
    problema: Optional[str]


def _revisar(rooms: Sequence) -> List[_RecintoRevisado]:
    """Clasifica y valida cada recinto por separado, sin decidir todavía nada
    sobre la vivienda: primero se reúne toda la evidencia, luego se concluye."""
    revisados: List[_RecintoRevisado] = []
    for room in rooms:
        etiqueta = (getattr(room, "label", None) or "(sin rotulo)").strip()
        poligono = getattr(room, "polygon", None)
        problema = None
        if poligono is None or getattr(poligono, "is_empty", True):
            problema = GEOMETRIA_AUSENTE
            poligono = None
        elif not poligono.is_valid:
            problema = GEOMETRIA_INVALIDA
        elif poligono.area < AREA_MINIMA_M2:
            problema = GEOMETRIA_AUSENTE
        revisados.append(
            _RecintoRevisado(
                etiqueta=etiqueta,
                clase=clasificar_recinto(getattr(room, "label", None)),
                poligono=poligono,
                problema=problema,
            )
        )
    return revisados


def _solapes(revisados: Sequence[_RecintoRevisado]) -> List[Tuple[str, str, float]]:
    """Pares de recintos cuyos polígonos comparten área por encima de la
    tolerancia. Devuelve hallazgos, no todas las combinaciones."""
    utiles = [r for r in revisados if r.poligono is not None and r.problema is None]
    encontrados: List[Tuple[str, str, float]] = []
    for i in range(len(utiles)):
        for j in range(i + 1, len(utiles)):
            a, b = utiles[i], utiles[j]
            try:
                compartida = a.poligono.intersection(b.poligono).area
            except Exception:  # noqa: BLE001 - geometría ajena mal formada
                continue
            if compartida > TOLERANCIA_SOLAPE_M2:
                encontrados.append((a.etiqueta, b.etiqueta, compartida))
    return encontrados


def _superficie_util(
    unit,
    *,
    nombre: str,
    clases_incluidas: Tuple[str, ...],
    explicacion_clase: str,
) -> Hecho:
    """Núcleo compartido de las dos superficies del módulo (ver más abajo).

    Las dos difieren únicamente en qué clases entran en la unión final —
    `OCUPABLE` sola, o `OCUPABLE` + `OCUPACION_NULA`—; el resto del contrato
    (validación de geometría, detección de solape, motivo de `AMBIGUO`) es
    idéntico porque responde a la misma pregunta: ¿se puede confiar en la
    geometría de esta vivienda? Un solape entre CUALQUIER par de recintos
    invalida la lectura entera, sea cual sea la clase de esos recintos.
    """
    ambito = f"vivienda {getattr(unit, 'name', '(sin nombre)')}"
    comun = dict(
        nombre=nombre,
        ambito=ambito,
        tipo="derivado",
        unidad="m2",
        fuente="poligonos de la capa de areas del DXF",
        referencia_normativa=DEFINICION_CONCEPT_ID,
        criterio_declarado=(
            "DB-SI Anejo SI A: superficie en planta de un recinto, sector o "
            "edificio ocupable por las personas"
        ),
    )

    rooms = list(getattr(unit, "rooms", ()) or ())
    if not rooms:
        return Hecho(
            **comun, estado=UNKNOWN,
            motivos=(Motivo(SIN_RECINTOS, "La vivienda no tiene ningun recinto."),),
            explicacion="No se puede medir la superficie de una vivienda sin recintos.",
        )

    revisados = _revisar(rooms)
    motivos: List[Motivo] = []

    # 1. Geometría rota. Va primero porque invalida cualquier medición
    #    posterior: sin polígono no hay ni clasificación que valga.
    ausentes = [r for r in revisados if r.problema == GEOMETRIA_AUSENTE]
    invalidas = [r for r in revisados if r.problema == GEOMETRIA_INVALIDA]
    if ausentes:
        motivos.append(Motivo(
            GEOMETRIA_AUSENTE,
            "Sin geometria utilizable: %s." % ", ".join(r.etiqueta for r in ausentes),
        ))
    if invalidas:
        motivos.append(Motivo(
            GEOMETRIA_INVALIDA,
            "Poligono invalido (se cruza a si mismo o esta mal cerrado): %s."
            % ", ".join(r.etiqueta for r in invalidas),
        ))

    # 2. Solape. La unión lo taparía; se declara en su lugar.
    solapados = _solapes(revisados)
    if solapados:
        motivos.append(Motivo(
            SOLAPE_NO_RESUELTO,
            "Recintos que comparten superficie: %s. No se puede saber cual es "
            "el recinto real, asi que no se publica un area." % "; ".join(
                "%s y %s comparten %.2f m2" % (a, b, m2) for a, b, m2 in solapados
            ),
        ))

    # 3. Clasificación. Terraza y tendedero caen aquí.
    ambiguos = [r for r in revisados if r.clase == AMBIGUO and r.problema is None]
    if ambiguos:
        motivos.append(Motivo(
            RECINTO_AMBIGUO,
            "No consta si estos recintos son superficie ocupable segun el "
            "DB-SI: %s. El Anejo SI A no los nombra y el plano no dice si "
            "quedan dentro de la envolvente." % ", ".join(r.etiqueta for r in ambiguos),
        ))

    computables = [
        r for r in revisados
        if r.problema is None and r.clase in clases_incluidas
    ]
    diagnostico = {
        "recintos": [(r.etiqueta, r.clase, r.problema) for r in revisados],
        "solapes": solapados,
        "n_computables": len(computables),
    }
    if computables:
        # Área de la unión, siempre — también cuando el hecho sale UNKNOWN.
        # Es diagnóstico para el humano que abra el plano, nunca el valor.
        union = unary_union([r.poligono for r in computables])
        diagnostico["area_union_m2"] = union.area
        diagnostico["area_suma_m2"] = sum(r.poligono.area for r in computables)

    if motivos:
        return Hecho(
            **comun, estado=UNKNOWN, motivos=tuple(motivos),
            procedencia=tuple(
                "%s -> %s" % (r.etiqueta, r.problema or r.clase) for r in revisados
            ),
            explicacion="Superficie util DB-SI no determinable: %s"
                        % motivos[0].detalle,
            diagnostico=diagnostico,
        )

    if not computables:
        return Hecho(
            **comun, estado=UNKNOWN,
            motivos=(Motivo(SIN_RECINTOS,
                            "Ningun recinto de la vivienda es computable."),),
            explicacion="No queda ningun recinto sobre el que medir.",
            diagnostico=diagnostico,
        )

    return Hecho(
        **comun,
        estado=KNOWN,
        valor=diagnostico["area_union_m2"],
        confianza=MEDIA,  # techo por clasificar via rotulo; ver docstring del modulo
        procedencia=tuple("%s -> %s" % (r.etiqueta, r.clase) for r in computables),
        explicacion=(
            "Union geometrica de %d recintos clasificados como %s segun DB-SI "
            "Anejo SI A." % (len(computables), explicacion_clase)
        ),
        diagnostico=diagnostico,
    )


def superficie_util_db_si(unit) -> Hecho:
    """El hecho `superficie_util_db_si` de una vivienda: TODA la superficie
    ocupable, incluidas las zonas de ocupación nula (que siguen siendo
    superficie útil, el Anejo SI A sólo las excluye del número de ocupantes).

    Devuelve siempre un `Hecho`, nunca `None` ni un float suelto: el contrato
    de lectura tiene cuatro estados y ninguno es el silencio
    (`DB-SI_FACT_MODEL.md` §6).
    """
    return _superficie_util(
        unit,
        nombre="superficie_util_db_si",
        clases_incluidas=(OCUPABLE, OCUPACION_NULA),
        explicacion_clase="superficie ocupable",
    )


def superficie_util_ocupable_db_si(unit) -> Hecho:
    """El hecho `superficie_util_ocupable_db_si` de una vivienda: la
    superficie útil que SÍ cuenta a efectos del número de ocupantes —
    excluye las zonas de ocupación nula, tal como exige el Anejo SI A para
    calcular ocupación (Tabla 2.1, CAP-3).

    Sigue siendo un subconjunto de `superficie_util_db_si`: ambas comparten
    la misma detección de solape y de recintos ambiguos, porque la pregunta
    "¿la geometría de esta vivienda es de fiar?" es una sola, no dos.
    """
    return _superficie_util(
        unit,
        nombre="superficie_util_ocupable_db_si",
        clases_incluidas=(OCUPABLE,),
        explicacion_clase="superficie ocupable a efectos de ocupacion (excluye ocupacion nula)",
    )


def superficie_util_db_si_por_unidad(units: Sequence) -> List[Hecho]:
    """El hecho de cada vivienda, en el mismo orden. Sin filtrar los UNKNOWN:
    una vivienda que no se puede medir tiene que seguir apareciendo, con su
    motivo — desaparecer sería el silencio que §6 prohíbe."""
    return [superficie_util_db_si(u) for u in units]


def superficie_util_ocupable_db_si_por_unidad(units: Sequence) -> List[Hecho]:
    """Igual que `superficie_util_db_si_por_unidad`, para CAP-3."""
    return [superficie_util_ocupable_db_si(u) for u in units]
