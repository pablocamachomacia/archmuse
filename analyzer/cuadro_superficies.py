# -*- coding: utf-8 -*-
"""Fase 2 — borrador de relleno del "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA".

Diseño de referencia: informe de Fase 1 de esta misma conversación (detección
del `ACAD_TABLE` en `v2s.dxf`, grid de 4 columnas × 14 filas, 24 MTEXT de
etiqueta/valor). Este módulo **no lee ningún DXF** y **no escribe nada**: solo
calcula, en memoria, qué texto debería llevar cada celda de valor y por qué.

Deliberadamente **separado de `parser.py` y de `evaluator.py`**:
- No importa `evaluator.py` — reimplementa localmente los patrones de
  etiqueta que necesita (mismo criterio de normalización que
  `evaluator._normalize`, duplicado a propósito para no acoplar este módulo
  al motor de reglas CTE; si `evaluator.py` cambia sus patrones, este módulo
  no debe cambiar con él sin que alguien lo decida explícitamente).
- No importa `parser.py` — recibe `Room`/`Unit` ya construidos, nunca abre
  un DXF.

### Las cuatro reglas de producto que gobiernan este módulo

1. **Estancia pedida por el cuadro que no existe en la vivienda → `0,00 m²`**
   (`CERO_REAL`). Es un hecho negativo verificado (se buscó y no hay ninguna),
   no una ausencia de información.
2. **Superficie que no puede conocerse de forma fiable → `N/D`**
   (`NO_DISPONIBLE`). Dato estructuralmente inalcanzable con lo que hay hoy
   (superficie construida sin espesores de muro; nº de unidades sin
   declaración de proyecto) — no es que falte buscar, es que no hay de dónde
   sacarlo.
3. **Ambigüedad real entre habitaciones → celda sin tocar** (`BLOQUEADO`).
   Cuando el cuadro pide N espacios de una familia (p. ej. 2 terrazas) y la
   geometría real no da exactamente N piezas inequívocas, la única acción
   honesta es no escribir nada y decir por qué — nunca repartir por orden de
   aparición ni sumar piezas que puedan no ser del mismo tipo.
4. **Nunca sobrescribir una celda ya rellenada.** Si el DXF ya trae un valor
   en una celda (p. ej. "VIVIENDA TIPO" → "VT1 /3"), este módulo lo conserva
   tal cual está escrito, no lo reformatea ni lo recalcula, y lo marca
   `escribir=False` para que la Fase 3 lo salte.

### Excepción documentada: "salón + cocina"

Es el único campo cuya etiqueta indica explícitamente una **unión**
("salón + cocina", no "salón" a secas). Por eso, y solo para este campo, dos
piezas que coincidan (una `Room` "Salón" y otra "Cocina", o directamente una
única `Room` "Salón/cocina") se **suman**, en vez de aplicar la regla general
de bloqueo por recuento múltiple. El resto de familias (dormitorio, baño,
aseo, vestíbulo, pasillo, tendedero, terraza) usan la regla general: más de
una pieza real para un único hueco del cuadro es una ambigüedad, no una suma.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Estados — catálogo cerrado de 4, tal como pide el encargo. No se amplía.
# ---------------------------------------------------------------------------

CALCULADO = "CALCULADO"
CERO_REAL = "CERO_REAL"
NO_DISPONIBLE = "NO_DISPONIBLE"
BLOQUEADO = "BLOQUEADO"

_ESTADOS_VALIDOS = (CALCULADO, CERO_REAL, NO_DISPONIBLE, BLOQUEADO)


def _normalizar(texto: str) -> str:
    """Mismo criterio que `evaluator._normalize`: sin acentos, en mayúsculas.

    Duplicado a propósito (ver docstring del módulo) — no se importa de
    `evaluator.py`.
    """
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.upper().strip()


def _formatear_area(valor_m2: float) -> str:
    """`21.9` -> `"21,90 m²"`. Formato español, 2 decimales, siempre con signo."""
    return ("%.2f m²" % valor_m2).replace(".", ",")


# ---------------------------------------------------------------------------
# Contrato de entrada: el cuadro ya detectado (Fase 1), como datos puros.
# `detectar_cuadro_superficies` (más abajo) construye esto a partir de un DXF
# real, pero la función de cálculo nunca ve un `Drawing` de ezdxf.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CeldaCuadro:
    """Una celda de VALOR del cuadro (no la celda de etiqueta)."""

    campo: str            # identificador estable: "salon_cocina", "dormitorio_1", ...
    etiqueta: str          # texto de la etiqueta tal cual aparece en el DXF
    columna: str            # "B" (valor interior) o "D" (valor exterior)
    x: float
    y: float
    texto_actual: Optional[str] = None  # contenido ya presente, o None si está vacía


@dataclass(frozen=True)
class CuadroSuperficies:
    """El cuadro detectado, ya reducido a datos: una celda de valor por campo."""

    celdas: Sequence[CeldaCuadro]

    def celda(self, campo: str) -> Optional[CeldaCuadro]:
        for c in self.celdas:
            if c.campo == campo:
                return c
        return None


# ---------------------------------------------------------------------------
# Salida: un `CeldaRelleno` por campo que el cuadro pida.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CeldaRelleno:
    campo: str
    texto: str                    # "21,90 m²" | "0,00 m²" | "N/D" | el texto ya existente
    estado: str                    # CALCULADO | CERO_REAL | NO_DISPONIBLE | BLOQUEADO
    motivo: Optional[str]          # por qué, cuando no es un CALCULADO limpio
    celda: Optional[CeldaCuadro]   # coordenada/celda destino (None si el cuadro no la trae)
    preexistente: bool = False     # True si la celda YA tenía texto en el DXF
    escribir: bool = True          # False si la Fase 3 debe saltarse esta celda
    # Fase 5: True si el valor lo aportó el arquitecto respondiendo una
    # `Solicitud` (nunca lo calculó ArchMuse a partir de la geometría). Se
    # guarda aparte de `preexistente` -- son dos procedencias distintas
    # ("ya estaba en el DXF" vs. "lo acaba de declarar el usuario") que no
    # deben confundirse en ningún consumidor futuro.
    declarado_por_usuario: bool = False

    def __post_init__(self) -> None:
        if self.estado not in _ESTADOS_VALIDOS:
            raise ValueError("estado %r fuera del catálogo cerrado %r" % (self.estado, _ESTADOS_VALIDOS))


# ---------------------------------------------------------------------------
# Familias de habitación — patrón de etiqueta (sobre texto normalizado) y,
# para las familias con más de un hueco en el cuadro (terraza 1/terraza 2),
# el orden de asignación cuando SÍ hay coincidencia exacta 1:1 por nombre.
# ---------------------------------------------------------------------------

_PATRON_SALON_COCINA = re.compile(r"SALON|COCINA")
_PATRON_PASILLO = re.compile(r"\bPASILLO\b|\bDISTRIBUIDOR\b|\bRECIBIDOR\b|\bHALL\b")
_PATRON_VESTIBULO = re.compile(r"\bVESTIBULO\b")
_PATRON_BANO = re.compile(r"\bBANO\b")  # "BAÑO" tras `_normalizar` (NFKD) -> "BANO", letra N literal
_PATRON_ASEO = re.compile(r"\bASEO\b")
_PATRON_TENDEDERO = re.compile(r"\bTENDEDERO\b")
_PATRON_TERRAZA = re.compile(r"\bTERRAZA\b")


def _patron_dormitorio(numero: int) -> re.Pattern:
    return re.compile(r"DORMITORIO\s*%d\b" % numero)


def _habitaciones_que_coinciden(rooms: Sequence, patron: re.Pattern) -> List:
    return [r for r in rooms if r.label and patron.search(_normalizar(r.label))]


# ---------------------------------------------------------------------------
# Regla general de una sola familia con UN hueco en el cuadro.
# ---------------------------------------------------------------------------


def _celda_preexistente(campo: str, celda: CeldaCuadro) -> CeldaRelleno:
    """La celda ya tenía texto en el DXF: se conserva tal cual, no se
    recalcula nada. Regla GENERAL (encontrada al probar contra `ejemplo.dxf`
    en la Fase 4 -- su cuadro llega con salón+cocina, tendedero, terraza 1,
    dormitorios, baño, aseo y nº de unidades ya declarados): "nunca
    sobrescribir una cifra existente" no es una excepción exclusiva de
    "VIVIENDA TIPO`, es la regla para las 18 celdas."""
    return CeldaRelleno(
        campo, celda.texto_actual, CALCULADO,
        "Ya había un valor en esta celda del DXF (%r); no se recalcula ni se sobrescribe." % celda.texto_actual,
        celda, preexistente=True, escribir=False,
    )


def _resolver_o_preexistente(campo: str, celda: Optional[CeldaCuadro], calculo) -> CeldaRelleno:
    """Punto de entrada único para los campos de un solo hueco: si la celda
    ya trae texto, se conserva (`_celda_preexistente`); si no, se delega en
    `calculo()` (una función sin argumentos, para no evaluar el cálculo real
    cuando no hace falta)."""
    if celda is not None and celda.texto_actual:
        return _celda_preexistente(campo, celda)
    return calculo()


def _celda_familia_simple(
    campo: str, celda: Optional[CeldaCuadro], rooms: Sequence, patron: re.Pattern,
    nombre_familia: str,
) -> CeldaRelleno:
    """0 coincidencias -> CERO_REAL. 1 -> CALCULADO. >1 -> BLOQUEADO (nunca se
    suman ni se elige una): el cuadro solo tiene un hueco para esta familia,
    así que más de una pieza real es una ambigüedad, no un dato con matices."""
    coincidencias = _habitaciones_que_coinciden(rooms, patron)
    if len(coincidencias) == 0:
        return CeldaRelleno(campo, _formatear_area(0.0), CERO_REAL,
                             "No existe ninguna estancia «%s» en esta vivienda." % nombre_familia,
                             celda)
    if len(coincidencias) == 1:
        return CeldaRelleno(campo, _formatear_area(coincidencias[0].area_m2), CALCULADO, None, celda)
    return CeldaRelleno(
        campo, "BLOQUEADO", BLOQUEADO,
        "El cuadro solo tiene un hueco para «%s», pero se han encontrado %d estancias "
        "con esa etiqueta (%s). No se reparte ni se suma sin que un humano decida cuál "
        "es la correcta." % (nombre_familia, len(coincidencias),
                              ", ".join("%.2f m2" % r.area_m2 for r in coincidencias)),
        celda, escribir=False,
    )


def _celda_salon_cocina(celda: Optional[CeldaCuadro], rooms: Sequence) -> CeldaRelleno:
    """Única excepción a la regla anterior -- ver docstring del módulo: la
    propia etiqueta ("salón + cocina") pide una suma, no una pieza única."""
    coincidencias = _habitaciones_que_coinciden(rooms, _PATRON_SALON_COCINA)
    if not coincidencias:
        return CeldaRelleno("salon_cocina", _formatear_area(0.0), CERO_REAL,
                             "No existe ninguna estancia «Salón» ni «Cocina» en esta vivienda.", celda)
    total = sum(r.area_m2 for r in coincidencias)
    return CeldaRelleno("salon_cocina", _formatear_area(total), CALCULADO, None, celda)


def _celdas_familia_multiple(
    campos: Sequence[str], celdas: Dict[str, Optional[CeldaCuadro]], rooms: Sequence,
    patron: re.Pattern, nombre_familia: str,
) -> List[CeldaRelleno]:
    """Familia con MÁS de un hueco en el cuadro (terraza 1, terraza 2, ...).

    Solo se calcula si el número de piezas reales coincide EXACTAMENTE con el
    número de huecos Y, además, cada pieza real trae en su propia etiqueta el
    número que le correspondería (p. ej. una `Room` literalmente etiquetada
    "Terraza 1"). Sin esa doble condición, asignar una pieza sin numerar a un
    hueco numerado sería inventar el reparto -- así que se bloquean todos los
    huecos de la familia a la vez, con el mismo motivo.

    Huecos que YA tienen texto en el DXF se conservan sin más (regla general,
    ver `_celda_preexistente`) y se sacan de la cuenta. Si queda un hueco
    vacío pero OTRO de la misma familia ya está declarado, no se completa el
    vacío: no hay forma fiable de saber qué pieza real corresponde al hueco
    ya escrito, así que restar esa pieza del recuento sería una suposición,
    no un hecho -- se bloquea el resto, con el motivo explicado."""
    preexistentes = [c for c in campos if celdas.get(c) is not None and celdas[c].texto_actual]
    vacios = [c for c in campos if c not in preexistentes]

    resultados_preexistentes = [_celda_preexistente(c, celdas[c]) for c in preexistentes]
    if not vacios:
        return resultados_preexistentes
    if preexistentes:
        motivo_mixto = (
            "Esta familia («%s») ya tiene %d de %d huecos con un valor declarado en el DXF (%s). "
            "ArchMuse no puede saber con seguridad qué pieza real corresponde a los huecos aún "
            "vacíos sin arriesgarse a repetir o mal asignar una habitación -- no se completa "
            "automáticamente." % (
                nombre_familia, len(preexistentes), len(campos),
                ", ".join("%s=%r" % (c, celdas[c].texto_actual) for c in preexistentes),
            )
        )
        return resultados_preexistentes + [
            CeldaRelleno(c, "BLOQUEADO", BLOQUEADO, motivo_mixto, celdas.get(c), escribir=False)
            for c in vacios
        ]

    # Ninguno preexistente: la lógica de conteo original, sobre TODOS los
    # huecos (== `vacios` aquí, ya que `preexistentes` está vacío).
    n_huecos = len(campos)
    coincidencias = _habitaciones_que_coinciden(rooms, patron)

    if len(coincidencias) == 0:
        return [CeldaRelleno(c, _formatear_area(0.0), CERO_REAL,
                              "No existe ninguna estancia «%s» en esta vivienda." % nombre_familia,
                              celdas.get(c))
                for c in campos]

    # ¿Cada pieza real numera exactamente uno de los huecos, sin ambigüedad?
    asignacion: Dict[str, object] = {}
    if len(coincidencias) == n_huecos:
        pendientes = list(coincidencias)
        for i, campo in enumerate(campos, start=1):
            patron_numerado = re.compile(patron.pattern + r"\s*%d\b" % i)
            emparejadas = [r for r in pendientes if patron_numerado.search(_normalizar(r.label))]
            if len(emparejadas) == 1:
                asignacion[campo] = emparejadas[0]
                pendientes.remove(emparejadas[0])
        if len(asignacion) == n_huecos:
            return [CeldaRelleno(c, _formatear_area(asignacion[c].area_m2), CALCULADO, None, celdas.get(c))
                    for c in campos]

    motivo = (
        "El cuadro tiene %d huecos para «%s», pero se han encontrado %d estancia(s) con esa "
        "etiqueta (%s) y ninguna indica en su propio nombre a qué número corresponde. "
        "Asignarlas por orden de aparición sería inventar el reparto -- no se hace." % (
            n_huecos, nombre_familia, len(coincidencias),
            ", ".join("%.2f m2" % r.area_m2 for r in coincidencias),
        )
    )
    return [CeldaRelleno(c, "BLOQUEADO", BLOQUEADO, motivo, celdas.get(c), escribir=False)
            for c in campos]


def _celda_no_disponible(campo: str, celda: Optional[CeldaCuadro], motivo: str) -> CeldaRelleno:
    return CeldaRelleno(campo, "N/D", NO_DISPONIBLE, motivo, celda)


def _celda_total(
    campo: str, celda: Optional[CeldaCuadro], componentes: Sequence[CeldaRelleno], etiqueta_total: str,
) -> CeldaRelleno:
    """Suma de un grupo de celdas ya resueltas. Si CUALQUIERA de los
    componentes está `BLOQUEADO`, el total se bloquea también -- sumar con un
    componente desconocido produciría una cifra falsa, no una aproximación
    razonable. `CERO_REAL` sí participa en la suma (es un cero verificado).

    Un componente PREEXISTENTE (Fase 4: descubierto en `ejemplo.dxf`, cuyo
    cuadro ya trae "21.90m2", "8.48"... en formatos que este módulo no
    genera) tampoco es sumable con garantías si su texto no está en el
    formato exacto de `_formatear_area` -- ver `_valor_numerico`. No se
    intenta interpretar un formato ajeno: se bloquea el total, con el mismo
    principio que un componente `BLOQUEADO`."""
    bloqueados = [c for c in componentes if c.estado == BLOQUEADO]
    if bloqueados:
        return CeldaRelleno(
            campo, "BLOQUEADO", BLOQUEADO,
            "%s no se calcula: depende de %s, que %s bloqueada por ambigüedad de habitaciones." % (
                etiqueta_total,
                ", ".join(c.campo for c in bloqueados),
                "está" if len(bloqueados) == 1 else "están",
            ),
            celda, escribir=False,
        )
    valores = [(c, _valor_numerico(c)) for c in componentes]
    no_sumables = [c for c, v in valores if v is None]
    if no_sumables:
        return CeldaRelleno(
            campo, "BLOQUEADO", BLOQUEADO,
            "%s no se calcula: %s (%s) ya tiene un valor declarado en el DXF en un formato que "
            "ArchMuse no puede sumar con garantías. No se inventa una conversión." % (
                etiqueta_total,
                "la celda" if len(no_sumables) == 1 else "las celdas",
                ", ".join("%s=%r" % (c.campo, c.texto) for c in no_sumables),
            ),
            celda, escribir=False,
        )
    total = sum(v for _c, v in valores)
    return CeldaRelleno(campo, _formatear_area(total), CALCULADO, None, celda)


def _valor_numerico(celda_rellena: CeldaRelleno) -> Optional[float]:
    """Lee el número de una celda ya resuelta (CALCULADO/CERO_REAL), solo si
    su texto está en el formato exacto que genera `_formatear_area`
    ("21,90 m²"). Devuelve `None` -- nunca una conversión aproximada -- si no
    lo está: típicamente una celda PREEXISTENTE cuyo texto lo escribió un
    humano en otro formato. Quien llame debe tratar `None` como "no sumable
    con garantías", nunca como 0."""
    m = re.fullmatch(r"(\d+),(\d{2}) m²", celda_rellena.texto.strip())
    if not m:
        return None
    return float(m.group(1) + "." + m.group(2))


# ---------------------------------------------------------------------------
# La función pública, pura: (vivienda, cuadro, habitaciones) -> [CeldaRelleno]
# ---------------------------------------------------------------------------


def calcular_relleno_cuadro(unit, cuadro: CuadroSuperficies, rooms: Sequence) -> List[CeldaRelleno]:
    """Borrador de relleno del cuadro de superficies para una vivienda.

    No escribe nada, no importa ezdxf, no toca `evaluator.py`. `unit` es el
    `Unit` ya analizado por ArchMuse (se usa solo para `unit.name`, al
    contrastar "VIVIENDA TIPO"); `rooms` son las `Room` reales de esa
    vivienda -- normalmente `unit.rooms`, pasadas aparte porque la firma que
    pide el encargo las separa explícitamente.
    """
    resultados: List[CeldaRelleno] = []

    # --- Interior, familias de un solo hueco ---------------------------
    # Cada campo pasa primero por `_resolver_o_preexistente`: si la celda ya
    # tiene texto en el DXF, se conserva sin más -- ver docstring de
    # `_celda_preexistente`. `lambda` para no ejecutar el cálculo cuando no
    # hace falta (evita recorrer `rooms` en balde en el caso preexistente).
    resultados.append(_resolver_o_preexistente(
        "salon_cocina", cuadro.celda("salon_cocina"),
        lambda: _celda_salon_cocina(cuadro.celda("salon_cocina"), rooms)))
    resultados.append(_resolver_o_preexistente(
        "pasillo", cuadro.celda("pasillo"),
        lambda: _celda_familia_simple("pasillo", cuadro.celda("pasillo"), rooms, _PATRON_PASILLO, "pasillo")))
    for n in (1, 2, 3):
        campo = "dormitorio_%d" % n
        resultados.append(_resolver_o_preexistente(
            campo, cuadro.celda(campo),
            (lambda campo=campo, n=n: _celda_familia_simple(
                campo, cuadro.celda(campo), rooms, _patron_dormitorio(n), "dormitorio %d" % n))))
    resultados.append(_resolver_o_preexistente(
        "bano", cuadro.celda("bano"),
        lambda: _celda_familia_simple("bano", cuadro.celda("bano"), rooms, _PATRON_BANO, "baño")))
    resultados.append(_resolver_o_preexistente(
        "aseo", cuadro.celda("aseo"),
        lambda: _celda_familia_simple("aseo", cuadro.celda("aseo"), rooms, _PATRON_ASEO, "aseo")))
    resultados.append(_resolver_o_preexistente(
        "vestibulo", cuadro.celda("vestibulo"),
        lambda: _celda_familia_simple("vestibulo", cuadro.celda("vestibulo"), rooms, _PATRON_VESTIBULO, "vestíbulo")))

    # --- Exterior: tendedero (1 hueco) + terraza (2 huecos) -------------
    resultados.append(_resolver_o_preexistente(
        "tendedero", cuadro.celda("tendedero"),
        lambda: _celda_familia_simple("tendedero", cuadro.celda("tendedero"), rooms, _PATRON_TENDEDERO, "tendedero")))
    # `_celdas_familia_multiple` gestiona sus propios preexistentes (puede
    # haber uno de los dos huecos ya escrito y el otro no, como en
    # `ejemplo.dxf`: terraza 1 declarada, terraza 2 vacía).
    resultados.extend(_celdas_familia_multiple(
        ["terraza_1", "terraza_2"],
        {"terraza_1": cuadro.celda("terraza_1"), "terraza_2": cuadro.celda("terraza_2")},
        rooms, _PATRON_TERRAZA, "terraza",
    ))

    por_campo = {c.campo: c for c in resultados}

    # --- Totales, en cascada sobre lo ya resuelto -----------------------
    componentes_interior = [por_campo[c] for c in (
        "salon_cocina", "pasillo", "dormitorio_1", "dormitorio_2", "dormitorio_3",
        "bano", "aseo", "vestibulo",
    )]
    total_interior = _celda_total("total_util_interior", cuadro.celda("total_util_interior"),
                                   componentes_interior, "TOTAL SUP.UTIL INTERIOR")
    resultados.append(total_interior)
    por_campo["total_util_interior"] = total_interior

    componentes_exterior = [por_campo[c] for c in ("tendedero", "terraza_1", "terraza_2")]
    total_exterior = _celda_total("total_util_exterior", cuadro.celda("total_util_exterior"),
                                   componentes_exterior, "TOTAL SUP.UTIL EXTERIOR")
    resultados.append(total_exterior)
    por_campo["total_util_exterior"] = total_exterior

    # "TOTAL S. ÚTIL" -- interior + exterior, en la celda de columna B
    # (decisión de producto ya fijada por el encargo).
    resultados.append(_celda_total("total_util", cuadro.celda("total_util"),
                                    [total_interior, total_exterior], "TOTAL S. ÚTIL"))

    # --- Superficies construidas: siempre N/D en esta fase --------------
    motivo_construida = (
        "ArchMuse mide superficie útil a cara interior de muro; no conoce el espesor de "
        "los muros ni tiene capas AM_* suficientes en este proyecto para reconstruir la "
        "envolvente construida (docs/design/DB-SI_FACT_MODEL.md §3.3: reconstrucción por "
        "casco convexo medida con error del -24% al +49%). No se aproxima."
    )
    resultados.append(_resolver_o_preexistente(
        "superficie_construida_cerrada", cuadro.celda("superficie_construida_cerrada"),
        lambda: _celda_no_disponible("superficie_construida_cerrada",
                                      cuadro.celda("superficie_construida_cerrada"), motivo_construida)))
    resultados.append(_resolver_o_preexistente(
        "superficie_construida_exterior", cuadro.celda("superficie_construida_exterior"),
        lambda: _celda_no_disponible("superficie_construida_exterior",
                                      cuadro.celda("superficie_construida_exterior"), motivo_construida)))

    # --- Número de unidades: dato de proyecto, no de esta geometría -----
    # Salvo que ya esté declarado en el DXF (Fase 4, `ejemplo.dxf`: "NUMERO
    # UDS: 8") -- ahí también manda la regla general de no sobrescribir.
    resultados.append(_resolver_o_preexistente(
        "numero_unidades", cuadro.celda("numero_unidades"),
        lambda: _celda_no_disponible(
            "numero_unidades", cuadro.celda("numero_unidades"),
            "El número de unidades de este tipo en el edificio es un dato del proyecto "
            "(cuántas viviendas iguales a ésta hay), no algo derivable de la geometría de "
            "una sola vivienda. Requiere declaración explícita del arquitecto.",
        )))

    # --- Vivienda tipo: conservar si ya está bien, nunca sobrescribir ---
    resultados.append(_celda_vivienda_tipo(cuadro.celda("vivienda_tipo"), unit))

    return resultados


def _celda_vivienda_tipo(celda: Optional[CeldaCuadro], unit) -> CeldaRelleno:
    nombre_unidad = _normalizar(unit.name).replace(" ", "")
    if celda is not None and celda.texto_actual:
        texto_existente = _normalizar(celda.texto_actual).replace(" ", "")
        if texto_existente == nombre_unidad:
            return CeldaRelleno(
                "vivienda_tipo", celda.texto_actual, CALCULADO,
                "Ya declarado en el DXF y coincide con la vivienda analizada por ArchMuse "
                "(%s); no se sobrescribe." % unit.name,
                celda, preexistente=True, escribir=False,
            )
        return CeldaRelleno(
            "vivienda_tipo", celda.texto_actual, BLOQUEADO,
            "La celda ya tiene un valor (%r) que NO coincide con la vivienda analizada "
            "por ArchMuse (%r). No se sobrescribe una cifra existente ante una "
            "discrepancia -- requiere revisión humana." % (celda.texto_actual, unit.name),
            celda, preexistente=True, escribir=False,
        )
    return CeldaRelleno("vivienda_tipo", unit.name, CALCULADO, None, celda)


# ---------------------------------------------------------------------------
# Fase 5 — "Datos necesarios para completar el cuadro".
#
# `calcular_relleno_cuadro` ya deja dicho, campo a campo, CUÁLES no se
# pudieron resolver (BLOQUEADO/NO_DISPONIBLE) y POR QUÉ. Esta sección no
# vuelve a decidir nada de eso -- solo traduce esos motivos ya calculados en
# preguntas concretas (`detectar_solicitudes`) y, con las respuestas del
# arquitecto, produce un `CeldaRelleno` nuevo por campo (`aplicar_respuestas`)
# con el mismo contrato de siempre (mismo catálogo cerrado de 4 estados,
# mismas reglas de "nunca sobrescribir"). Sigue sin escribir nada, sin
# importar ezdxf: recibe y devuelve los mismos `CeldaRelleno` de Fase 2.
# ---------------------------------------------------------------------------

TIPO_ASIGNACION = "asignacion"
TIPO_NUMERICO = "numerico"
_TIPOS_SOLICITUD = (TIPO_ASIGNACION, TIPO_NUMERICO)

_ETIQUETA_CAMPO = {
    "tendedero": "Tendedero", "terraza_1": "Terraza 1", "terraza_2": "Terraza 2",
    "superficie_construida_cerrada": "Superficie construida cerrada",
    "superficie_construida_exterior": "Superficie construida exterior",
    "numero_unidades": "Número de unidades",
}


@dataclass(frozen=True)
class CandidatoAsignacion:
    """Una pieza real (`Room`) candidata a ocupar uno de los huecos de un
    grupo de asignación. `id` es estable DENTRO de una `Solicitud` concreta
    (mismo orden que produce `rooms`), no un identificador global -- el
    frontend lo devuelve tal cual al responder, `aplicar_respuestas` vuelve
    a generar la misma lista en el mismo orden para resolverlo."""

    id: str
    room_label: str
    area_m2: float
    x: float  # centroide del polígono real, para mostrar "dónde está" sin ambigüedad
    y: float


@dataclass(frozen=True)
class Solicitud:
    """Una pregunta que ArchMuse necesita hacerle al arquitecto para poder
    terminar el cuadro. `campos` son los huecos del cuadro que esta
    solicitud, una vez respondida, resuelve -- puede ser más de uno (el
    grupo exterior de `v2s.dxf` resuelve tres huecos con una sola
    pregunta de asignación)."""

    id: str
    tipo: str
    campos: Sequence[str]
    titulo: str
    ayuda: str
    candidatos: Sequence[CandidatoAsignacion] = ()  # solo tipo == TIPO_ASIGNACION
    unidad: Optional[str] = None                     # solo tipo == TIPO_NUMERICO

    def __post_init__(self) -> None:
        if self.tipo not in _TIPOS_SOLICITUD:
            raise ValueError("tipo de solicitud %r fuera del catálogo cerrado %r" % (self.tipo, _TIPOS_SOLICITUD))


# Grupos de asignación: campos del cuadro cuyas piezas candidatas se buscan
# juntas porque comparten la misma familia visual en el cuadro ("ESPACIOS
# EXTERIORES") y, verificado en `v2s.dxf`, pueden estar mal etiquetadas
# entre sí (dos "Tendedero" y una "Terraza" para tres huecos). Solo hay un
# grupo definido por ahora -- añadir uno de interior exigiría el mismo
# cuidado de diseño, no una entrada más en esta lista sin pensarlo.
_GRUPOS_ASIGNACION = [
    {
        "id": "asignacion_exterior",
        "campos": ("tendedero", "terraza_1", "terraza_2"),
        "patrones": (_PATRON_TENDEDERO, _PATRON_TERRAZA),
        "titulo": "¿Qué pieza del plano es cada espacio exterior?",
        "ayuda": (
            "El cuadro pide tendedero, terraza 1 y terraza 2, pero ArchMuse ha encontrado "
            "estas piezas con esas etiquetas en el plano y no puede saber, solo por el nombre, "
            "cuál corresponde a cada hueco. Asigna cada pieza real al hueco que le corresponda "
            "(o déjala sin asignar si no es ninguno de los tres)."
        ),
    },
]

# Solicitudes numéricas: (campo, título, ayuda, unidad, formateador de la
# respuesta a texto de celda). `numero_unidades` no lleva "m²" -- ver
# `_formatear_entero`.
_SOLICITUDES_NUMERICAS = [
    (
        "superficie_construida_cerrada", "Superficie construida cerrada",
        "ArchMuse no puede medir esta magnitud sin el espesor de los muros (ver el motivo de "
        "la celda). Indica la superficie construida cerrada de esta vivienda, en m².",
        "m²",
    ),
    (
        "superficie_construida_exterior", "Superficie construida exterior",
        "Mismo motivo que la anterior: indica la superficie construida exterior de esta "
        "vivienda, en m².",
        "m²",
    ),
    (
        "numero_unidades", "Número de unidades",
        "Cuántas viviendas de este mismo tipo tiene el edificio -- es un dato del proyecto, "
        "no de esta geometría.",
        "uds",
    ),
]


def _formatear_entero(valor) -> str:
    """Para `numero_unidades`: sin decimales, sin unidad -- mismo formato que
    ya usa `ejemplo.dxf` cuando lo declara un humano ("8", no "8 uds")."""
    return str(int(round(float(valor))))


def _candidatos_grupo(grupo: dict, rooms: Sequence) -> List[CandidatoAsignacion]:
    """Misma lista, en el mismo orden, para `detectar_solicitudes` y para
    `aplicar_respuestas` -- es lo que permite que los `id` ("cand_0", ...)
    generados en un lado sigan significando lo mismo en el otro, aunque
    nunca se guarde nada entre una llamada y la siguiente."""
    encontrados: List = []
    for patron in grupo["patrones"]:
        encontrados.extend(_habitaciones_que_coinciden(rooms, patron))
    return [
        CandidatoAsignacion(id="cand_%d" % i, room_label=r.label, area_m2=r.area_m2,
                             x=r.polygon.centroid.x, y=r.polygon.centroid.y)
        for i, r in enumerate(encontrados)
    ]


def detectar_solicitudes(resultados: Sequence[CeldaRelleno], rooms: Sequence) -> List[Solicitud]:
    """Qué hace falta preguntarle al arquitecto para poder completar el
    cuadro -- lista vacía si `resultados` ya no tiene ningún `BLOQUEADO` ni
    `NO_DISPONIBLE` sin resolver (nada que preguntar, se puede descargar
    directamente)."""
    por_campo = {r.campo: r for r in resultados}
    solicitudes: List[Solicitud] = []

    for grupo in _GRUPOS_ASIGNACION:
        pendientes = [c for c in grupo["campos"] if por_campo[c].estado == BLOQUEADO]
        if not pendientes:
            continue
        solicitudes.append(Solicitud(
            id=grupo["id"], tipo=TIPO_ASIGNACION, campos=tuple(pendientes),
            titulo=grupo["titulo"], ayuda=grupo["ayuda"],
            candidatos=tuple(_candidatos_grupo(grupo, rooms)),
        ))

    for campo, titulo, ayuda, unidad in _SOLICITUDES_NUMERICAS:
        r = por_campo.get(campo)
        if r is not None and r.estado == NO_DISPONIBLE and not r.preexistente:
            solicitudes.append(Solicitud(id=campo, tipo=TIPO_NUMERICO, campos=(campo,),
                                          titulo=titulo, ayuda=ayuda, unidad=unidad))

    return solicitudes


def celdas_sin_resolver(resultados: Sequence[CeldaRelleno]) -> List[CeldaRelleno]:
    """Las que quedan `BLOQUEADO`/`NO_DISPONIBLE` -- lista vacía significa
    "el cuadro está completo, se puede descargar la versión final"."""
    return [r for r in resultados if r.estado in (BLOQUEADO, NO_DISPONIBLE)]


def aplicar_respuestas(
    resultados: Sequence[CeldaRelleno], rooms: Sequence, respuestas: Sequence[dict],
) -> List[CeldaRelleno]:
    """Aplica las respuestas del arquitecto sobre el resultado ya calculado
    por `calcular_relleno_cuadro` y devuelve una lista nueva (no muta
    `resultados`). Recalcula los totales que dependan de algo que acaba de
    cambiar, con la misma `_celda_total` de siempre -- no hay una segunda
    fórmula de suma en esta sección.

    Cada `respuesta` es un dict:
      - numérica:   {"tipo": "numerico", "campo": "...", "valor": 65.4}
      - asignación: {"tipo": "asignacion", "solicitud_id": "...",
                      "asignaciones": {"tendedero": "cand_1", "terraza_1": null, ...}}

    **Nunca sobrescribe una celda que ya tenga texto en el DXF.** Es una red
    de seguridad, no el camino normal: `detectar_solicitudes` ya no pregunta
    por una celda preexistente, así que esto solo puede dispararse si a
    `aplicar_respuestas` le llega una respuesta para un campo que, en el
    DXF real, resultó estar ya escrito -- se bloquea con el conflicto
    explicado, nunca se pisa el valor existente."""
    por_campo: Dict[str, CeldaRelleno] = {r.campo: r for r in resultados}

    def _con_conflicto_o(campo: str, texto_nuevo: str, construir) -> CeldaRelleno:
        actual = por_campo[campo]
        if actual.celda is not None and actual.celda.texto_actual:
            if _normalizar(actual.celda.texto_actual) != _normalizar(texto_nuevo):
                return CeldaRelleno(
                    campo, actual.celda.texto_actual, BLOQUEADO,
                    "Conflicto: el DXF ya tiene %r en esta celda, y la respuesta declarada "
                    "(%r) es distinta. No se sobrescribe -- revisa cuál de las dos es la "
                    "correcta antes de continuar." % (actual.celda.texto_actual, texto_nuevo),
                    actual.celda, preexistente=True, escribir=False,
                )
            # Coincide con lo ya escrito: se conserva el texto original, no
            # se pisa por el declarado aunque sean equivalentes.
            return CeldaRelleno(campo, actual.celda.texto_actual, CALCULADO,
                                 "Ya declarado en el DXF, coincide con la respuesta.",
                                 actual.celda, preexistente=True, escribir=False)
        return construir()

    for resp in respuestas:
        tipo = resp.get("tipo")
        if tipo == TIPO_NUMERICO:
            campo = resp["campo"]
            if campo not in por_campo:
                raise ValueError("respuesta numérica para un campo desconocido: %r" % campo)
            formatear = _formatear_entero if campo == "numero_unidades" else _formatear_area
            texto = formatear(resp["valor"])
            celda_destino = por_campo[campo].celda
            por_campo[campo] = _con_conflicto_o(
                campo, texto,
                lambda campo=campo, texto=texto, celda_destino=celda_destino: CeldaRelleno(
                    campo, texto, CALCULADO, "Declarado por el arquitecto.",
                    celda_destino, declarado_por_usuario=True,
                ),
            )
        elif tipo == TIPO_ASIGNACION:
            grupo = next((g for g in _GRUPOS_ASIGNACION if g["id"] == resp.get("solicitud_id")), None)
            if grupo is None:
                raise ValueError("solicitud_id de asignación desconocido: %r" % resp.get("solicitud_id"))
            candidatos = {c.id: c for c in _candidatos_grupo(grupo, rooms)}
            asignaciones = resp.get("asignaciones") or {}
            elegidos = [v for v in asignaciones.values() if v]
            if len(elegidos) != len(set(elegidos)):
                raise ValueError("una misma pieza no puede asignarse a dos huecos a la vez: %r" % asignaciones)
            for campo in grupo["campos"]:
                cand_id = asignaciones.get(campo)
                celda_destino = por_campo[campo].celda
                if cand_id:
                    if cand_id not in candidatos:
                        raise ValueError("candidato %r no existe en esta solicitud" % cand_id)
                    cand = candidatos[cand_id]
                    texto = _formatear_area(cand.area_m2)
                    por_campo[campo] = _con_conflicto_o(
                        campo, texto,
                        lambda campo=campo, texto=texto, celda_destino=celda_destino: CeldaRelleno(
                            campo, texto, CALCULADO,
                            "Declarado por el arquitecto (asignación de pieza real).",
                            celda_destino, declarado_por_usuario=True,
                        ),
                    )
                else:
                    # El arquitecto confirma explícitamente que no hay pieza
                    # real para este hueco -- es un cero declarado, no un
                    # cero automático (por eso CERO_REAL con
                    # declarado_por_usuario=True, no la rama CERO_REAL de
                    # `_celda_familia_simple`).
                    texto = _formatear_area(0.0)
                    por_campo[campo] = _con_conflicto_o(
                        campo, texto,
                        lambda campo=campo, texto=texto, celda_destino=celda_destino: CeldaRelleno(
                            campo, texto, CERO_REAL,
                            "El arquitecto confirma que no hay ninguna pieza real para este hueco.",
                            celda_destino, declarado_por_usuario=True,
                        ),
                    )
        else:
            raise ValueError("tipo de respuesta desconocido: %r" % tipo)

    # Recalcular los totales en cascada, con la MISMA función que los
    # calculó la primera vez -- ninguna fórmula nueva.
    componentes_interior = [por_campo[c] for c in (
        "salon_cocina", "pasillo", "dormitorio_1", "dormitorio_2", "dormitorio_3",
        "bano", "aseo", "vestibulo",
    )]
    total_interior = _celda_total("total_util_interior", por_campo["total_util_interior"].celda,
                                   componentes_interior, "TOTAL SUP.UTIL INTERIOR")
    por_campo["total_util_interior"] = total_interior

    componentes_exterior = [por_campo[c] for c in ("tendedero", "terraza_1", "terraza_2")]
    total_exterior = _celda_total("total_util_exterior", por_campo["total_util_exterior"].celda,
                                   componentes_exterior, "TOTAL SUP.UTIL EXTERIOR")
    por_campo["total_util_exterior"] = total_exterior

    por_campo["total_util"] = _celda_total("total_util", por_campo["total_util"].celda,
                                            [total_interior, total_exterior], "TOTAL S. ÚTIL")

    # Mismo orden que `resultados` de entrada, para que la salida sea estable.
    return [por_campo[r.campo] for r in resultados]


# ---------------------------------------------------------------------------
# Detección (IMPURA -- lee ezdxf). Separada a propósito de
# `calcular_relleno_cuadro`: esta función construye el `CuadroSuperficies`
# de entrada a partir de un DXF real; `calcular_relleno_cuadro` nunca sabe
# que ezdxf existe. Implementa el hallazgo de la Fase 1: el cuadro es un
# `ACAD_TABLE` cuyo título identifica la tabla sin depender de coordenadas
# fijas -- las coordenadas se leen de la rejilla de LINE de cada archivo.
# ---------------------------------------------------------------------------

TITULO_CUADRO = "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"

# Texto de etiqueta normalizado (sin acentos, sin puntuación final, en
# mayúsculas) -> campo. Es la única parte de este módulo que depende de la
# redacción exacta de ESTE cuadro; detectar_cuadro_superficies() ya deja
# dicho en su docstring que otra redacción exigiría ampliar esta tabla, no
# tocar la rejilla ni el resto de la detección.
_ETIQUETA_A_CAMPO = {
    "SALON + COCINA": "salon_cocina",
    "PASILLO": "pasillo",
    "DORMITORIO 1": "dormitorio_1",
    "DORMITORIO 2": "dormitorio_2",
    "DORMITORIO 3": "dormitorio_3",
    "BANO": "bano",
    "ASEO": "aseo",
    "VESTIBULO": "vestibulo",
    "TENDEDERO": "tendedero",
    "TERRAZA 1": "terraza_1",
    "TERRAZA 2": "terraza_2",
    "TOTAL SUP.UTIL INTERIOR (M2)": "total_util_interior",
    "TOTAL SUP.UTIL EXTERIOR (M2)": "total_util_exterior",
    "TOTAL S. UTIL (M2)": "total_util",
    "S. CONSTRUIDA CERRADA": "superficie_construida_cerrada",
    "S.CONSTRUIDA EXTERIOR": "superficie_construida_exterior",
    "VIVIENDA TIPO": "vivienda_tipo",
    "NUMERO UDS": "numero_unidades",
}


def _normalizar_etiqueta(texto: str) -> str:
    t = _normalizar(texto)
    t = t.rstrip(".:")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def detectar_cuadro_superficies(doc) -> Optional[CuadroSuperficies]:
    """Busca el `ACAD_TABLE` "CUADRO DE SUPERFICIES..." en `doc` (un
    `ezdxf.document.Drawing` ya cargado) y devuelve su `CuadroSuperficies`,
    o `None` si no se encuentra ninguno con ese título.

    Detección por **encabezado**, no por coordenadas fijas (Fase 1, punto 6):
    cualquier `ACAD_TABLE` de `doc.modelspace()` cuyo primer MTEXT normalizado
    sea `TITULO_CUADRO` se acepta; la rejilla de celdas se reconstruye en cada
    caso a partir de las LINE de ESE `ACAD_TABLE`, no de una tabla fija.
    """
    msp = doc.modelspace()
    for tabla in msp.query("ACAD_TABLE"):
        entidades = list(tabla.virtual_entities())
        mtexts = [e for e in entidades if e.dxftype() == "MTEXT"]
        lines = [e for e in entidades if e.dxftype() == "LINE"]
        titulos = [m for m in mtexts if _normalizar(m.text) == TITULO_CUADRO]
        if not titulos:
            continue
        return _construir_cuadro(mtexts, lines)
    return None


def _construir_cuadro(mtexts: Sequence, lines: Sequence) -> CuadroSuperficies:
    # Rejilla: coordenadas únicas de las verticales/horizontales.
    xs = sorted({round(v, 3) for ln in lines for v in (ln.dxf.start.x, ln.dxf.end.x)})
    ys = sorted({round(v, 3) for ln in lines for v in (ln.dxf.start.y, ln.dxf.end.y)}, reverse=True)
    if len(xs) < 4:
        raise ValueError("la rejilla del cuadro tiene menos de 4 columnas (%d) -- no es el "
                          "layout de 4 columnas esperado (label/valor int, label/valor ext)" % len(xs))

    def _banda(valor: float, cortes: Sequence[float]) -> int:
        for i in range(len(cortes) - 1):
            lo, hi = sorted((cortes[i], cortes[i + 1]))
            if lo - 1e-6 <= valor <= hi + 1e-6:
                return i
        return -1

    # Columnas: 0=label-int, 1=valor-int(B), 2=label-ext, 3=valor-ext(D).
    col_centro = [(xs[i] + xs[i + 1]) / 2 for i in range(len(xs) - 1)]

    etiquetas = []
    valores_existentes: Dict[tuple, str] = {}
    for m in mtexts:
        ip = m.dxf.insert
        col = _banda(ip.x, xs)
        fila = _banda(ip.y, ys)
        if col in (0, 2):
            etiquetas.append((fila, col, m.text, ip.x, ip.y))
        elif col in (1, 3):
            valores_existentes[(fila, col)] = m.text

    celdas = []
    for fila, col_etiqueta, texto_etiqueta, _lx, ly in etiquetas:
        campo = _ETIQUETA_A_CAMPO.get(_normalizar_etiqueta(texto_etiqueta))
        if campo is None:
            continue  # encabezado de grupo (p. ej. "ESPACIOS INTERIORES") o título -- no es un campo
        col_valor = col_etiqueta + 1  # label-int(0)->valor(1); label-ext(2)->valor(3)
        texto_actual = valores_existentes.get((fila, col_valor))
        celdas.append(CeldaCuadro(
            campo=campo,
            etiqueta=texto_etiqueta,
            columna="B" if col_valor == 1 else "D",
            x=col_centro[col_valor],
            y=ly,
            texto_actual=texto_actual,
        ))
    return CuadroSuperficies(celdas=celdas)
