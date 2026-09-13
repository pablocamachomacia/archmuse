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

1. **Estancia pedida por el cuadro que no existe en la vivienda → celda vacía**
   (`NO_DIBUJADA`), con su motivo. Hasta el 2026-09-13 era `0,00 m²`
   (`CERO_REAL`, «un hecho negativo verificado»); `D-13` lo deroga: ninguna
   habitación mide cero, así que un cero escrito es una cifra no medida.
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
import dataclasses
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

# `texto_dxf` no importa nada del proyecto: traerlo aquí no acopla este módulo
# a `parser.py` ni a `evaluator.py`, que es la separación que su docstring
# defiende.
from .emparejador_cuadro import emparejar
from .texto_dxf import decodificar_escapes

# ---------------------------------------------------------------------------
# Estados — catálogo cerrado de 4, tal como pide el encargo. No se amplía.
# ---------------------------------------------------------------------------

CALCULADO = "CALCULADO"
#: **`D-13` (Pablo, 2026-09-13), que deroga `C-4`: un `0,00 m²` no es nunca una
#: superficie válida de estancia.** Hasta ese día este estado se llamaba
#: `CERO_REAL` y escribía `0,00 m²` para una fila del cuadro que el plano no
#: dibuja. Verificado en AutoCAD: el cuadro del arquitecto pedía `pasillo` y
#: `vestibulo`, ese estudio mete el pasillo en el salón, y ArchMuse escribió dos
#: ceros. Una estancia no dibujada no mide cero: **no existe**, y la celda se
#: queda vacía con su motivo.
NO_DIBUJADA = "NO_DIBUJADA"
NO_DISPONIBLE = "NO_DISPONIBLE"
BLOQUEADO = "BLOQUEADO"

_ESTADOS_VALIDOS = (CALCULADO, NO_DIBUJADA, NO_DISPONIBLE, BLOQUEADO)


# ---------------------------------------------------------------------------
# Qué magnitud es cada campo del cuadro — catálogo cerrado y ÚNICO
# ---------------------------------------------------------------------------
#
# **Por qué existe esta sección.** Un cuadro de superficies tiene columnas que
# se parecen y no se suman entre sí. La superficie útil y la superficie
# construida miden lo mismo con criterios distintos (una a cara interior de
# muro, la otra incluyendo el muro): sumarlas no da una superficie mayor, da
# una cifra que no significa nada. Y `NUMERO UDS` no es una superficie en
# absoluto: es cuántas viviendas iguales tiene el edificio.
#
# Hasta hoy no había ningún sitio que dijera esto. Cada consumidor decidía por
# su cuenta qué celdas eran sumandos, y `agente/skills/superficies.py` lo
# decidía por el nombre —«si el campo contiene "total", no lo sumes»—, que deja
# fuera los totales y deja DENTRO la superficie construida y el número de
# unidades. Sobre `ejemplo.dxf`, cuyo cuadro trae «NUMERO UDS: 8», eso sumaba
# ocho metros cuadrados que no existen.
#
# Las cuatro tuplas de abajo son la respuesta, y son exhaustivas: hay un test
# (`tests/test_cuadro_superficies_magnitudes.py`) que falla si algún campo del
# cuadro no está clasificado en exactamente una de ellas. Un campo nuevo obliga
# a decidir qué magnitud es; no puede colarse como sumando por descuido.

#: Sumandos de la superficie útil INTERIOR. Es también, y no por casualidad, la
#: lista con la que `calcular_relleno_cuadro` calcula «TOTAL SUP.UTIL INTERIOR»:
#: una sola definición para el total del cuadro y para quien lo compruebe.
CAMPOS_UTIL_INTERIOR = (
    "salon_cocina", "pasillo", "dormitorio_1", "dormitorio_2", "dormitorio_3",
    "bano", "aseo", "vestibulo",
)

#: Sumandos de la superficie útil EXTERIOR (terrazas, tendederos).
CAMPOS_UTIL_EXTERIOR = ("tendedero", "terraza_1", "terraza_2")

#: Todo lo que suma superficie útil. Lo que se puede totalizar, y nada más.
CAMPOS_SUMANDOS_UTIL = CAMPOS_UTIL_INTERIOR + CAMPOS_UTIL_EXTERIOR

#: Totales ya calculados del propio cuadro. Sumarlos con sus partes duplicaría.
CAMPOS_TOTAL_UTIL = ("total_util_interior", "total_util_exterior", "total_util")

#: **`total_util` no se rellena nunca desde el 2026-09-08.** Es la celda que
#: sumaba útil interior y útil exterior en una sola cifra, y el arquitecto
#: dictaminó el 2026-09-07 que esas dos magnitudes no se suman: una terraza no
#: pesa en el cuadro lo mismo que un dormitorio, y el cómputo de los espacios
#: exteriores es criterio del técnico que firma, no de un programa.
#:
#: Se deja **`N/D` con este motivo escrito en el acta**, no en blanco: una celda
#: vacía se lee como «ArchMuse no ha sabido», y aquí sí ha sabido — ha decidido
#: no decidir por el arquitecto. Él puede escribirla a mano con su criterio.
#:
#: Ver `docs/design/2026-09-08-criterios-firmados-de-medicion.md`, criterio C-1.
MOTIVO_TOTAL_UTIL_NO_SE_SUMA = (
    "La superficie útil interior y la exterior no se suman en una sola cifra: el "
    "cómputo de terrazas y tendederos es criterio del técnico que firma (¿al 100 %, "
    "al 50 %, fuera del útil?) y ArchMuse no lo decide por él. Las dos magnitudes "
    "están arriba, cada una con su total. Esta celda se rellena a mano."
)

#: Superficie CONSTRUIDA. Es superficie y va en m², pero es otra magnitud: no
#: suma con la útil ni se cruza contra ella. ArchMuse no la calcula (no conoce
#: el espesor de los muros); cuando aparece con valor es porque el DXF la traía
#: o porque el arquitecto la declaró, y en los dos casos sigue sin ser un
#: sumando de la útil.
CAMPOS_CONSTRUIDA = ("superficie_construida_cerrada", "superficie_construida_exterior")

#: Campos que no son una superficie. `numero_unidades` es un contador de
#: viviendas y `vivienda_tipo` un rótulo.
CAMPOS_SIN_SUPERFICIE = ("numero_unidades", "vivienda_tipo")

#: Todos los campos del cuadro, en un solo sitio. El orden no significa nada.
CAMPOS_DEL_CUADRO = (
    CAMPOS_SUMANDOS_UTIL + CAMPOS_TOTAL_UTIL + CAMPOS_CONSTRUIDA + CAMPOS_SIN_SUPERFICIE
)


def _normalizar(texto: str) -> str:
    """Mismo criterio que `evaluator._normalize`: sin acentos, en mayúsculas.

    Duplicado a propósito (ver docstring del módulo) — no se importa de
    `evaluator.py`.

    Antes de nada se decodifican los escapes Unicode del DXF: la etiqueta del
    cuadro llega tal cual la escribió AutoCAD, y `sal\\U+00F3n + cocina` sin
    decodificar no es «SALON + COCINA» ni se parece. Es la misma conversión que
    aplica `parser._texto_de` al rótulo del plano, desde el mismo sitio, para
    que las dos mitades del emparejamiento hablen el mismo idioma.
    """
    texto = decodificar_escapes(texto)
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
    #: Posición en la rejilla de la tabla, base 0. Es lo que viaja al cliente
    #: CAD: `vla-SetText` pide fila y columna, no coordenadas. `x`/`y` siguen
    #: aquí porque la vía web escribe un MTEXT superpuesto y necesita el punto.
    fila: int = -1
    columna_indice: int = -1
    #: Dónde estaba la etiqueta de la que sale `columna_indice`. **Se guarda para
    #: que la relación entre las dos sea comprobable**: el valor va siempre a la
    #: celda de la derecha de su etiqueta, y un test lo verifica sobre cuadros
    #: que no son el de este estudio. Hasta el 2026-09-11 la columna de valor era
    #: una constante (1 y 3) y un cuadro con otra disposición recibía **cifras
    #: correctas en la columna equivocada**, sin error ni aviso.
    columna_etiqueta: int = -1


@dataclass(frozen=True)
class FilaDeCuadro:
    """Una fila del cuadro del arquitecto **tal cual está escrita**.

    Existe para poder **copiar su cuadro** al dibujar el de ArchMuse al lado
    (PRD `2026-09-12`, §4.4): la comparación sólo sirve si la fila N de una
    tabla es la fila N de la otra, y eso obliga a conservar **todas** las filas
    —encabezados de grupo, título y filas que ArchMuse no entiende incluidos—,
    con su redacción literal y su ortografía. `EXPACIOS INTERORES` se copia con
    su errata: corregirla sería editarle el documento por la puerta de atrás.

    `CuadroSuperficies.celdas` no sirve para esto y no se sustituye: aquella
    lista es «dónde va cada cifra» y tiene una entrada por campo reconocido;
    ésta es «cómo es su tabla» y tiene una entrada por fila, reconocida o no.
    """

    fila: int
    #: El texto de la etiqueta como está en el DXF. Nunca normalizado.
    etiqueta: str
    #: El campo que reclama, o `None` si es un encabezado, el título, o una fila
    #: que ArchMuse no ha sabido resolver.
    campo: Optional[str] = None
    #: Por qué no tiene campo, cuando lo parecía. `None` en un encabezado, que no
    #: es un fallo de nadie.
    motivo: Optional[str] = None
    #: En qué columna está la etiqueta, y en cuál su valor.
    #:
    #: **Su cuadro no es una lista de filas: son dos pares etiqueta/valor por
    #: fila** —los interiores a la izquierda, los exteriores a la derecha—, y
    #: por eso una misma `fila` aparece aquí varias veces. Aplanarlo a una
    #: columna al copiarlo perdería justo lo que hace útil la copia: que la
    #: fila N de la tabla de ArchMuse esté **a la misma altura** que la fila N
    #: de la suya cuando se dibujan una al lado de otra.
    columna_etiqueta: int = -1
    columna_valor: int = -1


@dataclass(frozen=True)
class CuadroSuperficies:
    """El cuadro detectado, ya reducido a datos: una celda de valor por campo."""

    celdas: Sequence[CeldaCuadro]
    #: Filas del cuadro que parecían pedir un campo y no se han podido resolver,
    #: con su motivo. No se rellenan y **no desaparecen**: se declaran (`C-6`).
    etiquetas_sin_campo: Sequence[tuple] = ()
    #: Todas sus filas, en orden y literales. Vacío en un cuadro construido a
    #: mano desde celdas sueltas (`cuadro_desde_celdas`), que no tiene tabla que
    #: copiar.
    filas: Sequence[FilaDeCuadro] = ()

    def celda(self, campo: str) -> Optional[CeldaCuadro]:
        for c in self.celdas:
            if c.campo == campo:
                return c
        return None

    def como_plantilla(self) -> "CuadroSuperficies":
        """El mismo cuadro con **todas las celdas de valor vacías**.

        ### Esto es el núcleo del cambio de diseño del 2026-09-12

        Hasta hoy, una celda con texto **impedía el cálculo**:
        `_resolver_o_preexistente` veía contenido y devolvía «ya había un valor,
        no se recalcula» sin llegar a medir nada. Era la forma correcta de
        cumplir «nunca sobrescribir» **mientras el destino era su celda**.

        Con destino propio deja de serlo, y el precio estaba medido: sobre
        `plantasimple.dxf`, de las 396 celdas de sus 22 cuadros emparejados,
        ArchMuse afirmaba **74 —y 73 eran `0,00 m²`—**. Calculando sobre la
        plantilla afirma **232, de las cuales 158 son cifras reales**. La
        diferencia no es una mejora: es la capacidad entera.

        **«Nunca sobrescribir» no se debilita, se cumple mejor.** Pasa de ser una
        regla del cálculo —frágil, porque depende de acertar qué celda está
        llena— a ser una propiedad de la arquitectura: su tabla no se toca
        porque no se escribe en ella.

        Lo que **sí** se conserva es su tabla como molde: mismas filas, mismo
        orden, mismas etiquetas. Se vacía el valor, no la forma.
        """
        return CuadroSuperficies(
            celdas=[dataclasses.replace(c, texto_actual=None) for c in self.celdas],
            etiquetas_sin_campo=tuple(self.etiquetas_sin_campo),
            filas=tuple(self.filas),
        )


# ---------------------------------------------------------------------------
# Salida: un `CeldaRelleno` por campo que el cuadro pida.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CeldaRelleno:
    campo: str
    texto: str                    # "21,90 m²" | "" | "N/D" | el texto ya existente -- nunca "0,00 m²" (D-13)
    estado: str                    # CALCULADO | NO_DIBUJADA | NO_DISPONIBLE | BLOQUEADO
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

# Las familias de la plantilla fija (decisión 3 de Pablo, 2026-09-13). Viven
# aquí, junto a las de arriba, para que el vocabulario siga siendo uno. **Las de
# arriba no se tocan**: sirven a las 18 filas fijas del cuadro clásico, donde
# «pasillo» incluye el distribuidor y «salón + cocina» es cualquiera de los dos.
# En la plantilla cada una es su propia familia.
_PATRON_SALON_Y_COCINA = re.compile(r"(?=.*\bSALON\b)(?=.*\bCOCINA\b)")
_PATRON_SOLO_SALON = re.compile(r"\bSALON\b")
_PATRON_SOLO_COCINA = re.compile(r"\bCOCINA\b")
_PATRON_SOLO_PASILLO = re.compile(r"\bPASILLO\b")
_PATRON_DISTRIBUIDOR = re.compile(r"\bDISTRIBUIDOR\b")
_PATRON_VESTIBULO_RECIBIDOR_HALL = re.compile(r"\bVESTIBULO\b|\bRECIBIDOR\b|\bHALL\b")
_PATRON_BALCON = re.compile(r"\bBALCON\b")
_PATRON_PORCHE = re.compile(r"\bPORCHE\b")


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
    """0 coincidencias -> NO_DIBUJADA (`D-13`). 1 -> CALCULADO. >1 -> BLOQUEADO
    (nunca se suman ni se elige una): el cuadro solo tiene un hueco para esta
    familia, así que más de una pieza real es una ambigüedad, no un dato con
    matices."""
    coincidencias = _habitaciones_que_coinciden(rooms, patron)
    if len(coincidencias) == 0:
        return _celda_no_dibujada(campo, celda, nombre_familia)
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
        return _celda_no_dibujada("salon_cocina", celda, "salón» ni «cocina")
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
        return [_celda_no_dibujada(c, celdas.get(c), nombre_familia) for c in campos]

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


def _celda_no_dibujada(campo: str, celda: Optional[CeldaCuadro], nombre_familia: str) -> CeldaRelleno:
    """El cuadro pide una fila que el plano no dibuja: **vacía, con motivo**."""
    return CeldaRelleno(
        campo, "", NO_DIBUJADA,
        "El plano no dibuja ninguna estancia «%s» en esta vivienda. No se escribe "
        "0,00 m²: ninguna habitación mide cero (D-13)." % nombre_familia,
        celda, escribir=False)


def _total_util_no_se_suma(celda: Optional[CeldaCuadro]) -> CeldaRelleno:
    """La celda «TOTAL S. ÚTIL», siempre `N/D` y siempre con su motivo.

    **No es una limitación de ArchMuse: es una decisión suya, y por eso lleva
    motivo en vez de quedarse en blanco.** Sumar útil interior y útil exterior
    produce una cifra que parece un total y no lo es — depende de un criterio de
    cómputo que firma un colegiado, no un programa. Antes esta celda se rellenaba
    con esa suma y viajaba dentro del DXF del cliente.
    """
    return CeldaRelleno(
        campo="total_util",
        texto="N/D",
        estado=NO_DISPONIBLE,
        motivo=MOTIVO_TOTAL_UTIL_NO_SE_SUMA,
        celda=celda,
    )


def _celda_total(
    campo: str, celda: Optional[CeldaCuadro], componentes: Sequence[CeldaRelleno], etiqueta_total: str,
) -> CeldaRelleno:
    """Suma de un grupo de celdas ya resueltas. Si CUALQUIERA de los
    componentes está `BLOQUEADO`, el total se bloquea también -- sumar con un
    componente desconocido produciría una cifra falsa, no una aproximación
    razonable. Una fila `NO_DIBUJADA` no participa: no es un cero, es una
    estancia que no existe (`D-13`). Si no queda ninguna, el total tampoco se
    escribe — un total de `0,00 m²` sería el mismo fallo un nivel más arriba.

    Un componente PREEXISTENTE (Fase 4: descubierto en `ejemplo.dxf`, cuyo
    cuadro ya trae "21.90m2", "8.48"... en formatos que este módulo no
    genera) tampoco es sumable con garantías si su texto no está en el
    formato exacto de `_formatear_area` -- ver `_valor_numerico`. No se
    intenta interpretar un formato ajeno: se bloquea el total, con el mismo
    principio que un componente `BLOQUEADO`.

    **DEFECTO CONOCIDO, sin corregir a 2026-09-03 (decisión de Pablo: la
    iteración estaba cerrada cuando se encontró).** Esta función **nunca mira
    `celda.texto_actual`**. Los otros quince campos del cuadro pasan por
    `_resolver_o_preexistente` y conservan lo que el DXF ya trae; los tres
    totales son los únicos que no. Consecuencia, reproducida: un cuadro que
    declara «TOTAL SUP.UTIL INTERIOR: 70,00 m²» sobre unas piezas que miden
    36,00 recibe un `CeldaRelleno("36,00 m²", CALCULADO, motivo=None,
    preexistente=False, escribir=True)` — se sobrescribe la cifra del
    arquitecto, se marca como calculada por ArchMuse, y **la discrepancia de
    34 m² no se declara en ningún sitio**.

    Rompe la regla 4 de este módulo («Nunca sobrescribir una celda ya
    rellenada») y la regla 5 del §4 de `CLAUDE.md` («Conflictos, no
    sobrescrituras… nunca elijas una fuente en silencio»). Y lo que se pierde
    es justo lo que el §1 declara como la razón por la que alguien paga:
    detectar que el cuadro de la memoria no cuadra con los planos antes de
    visar.

    No lo dispara ningún plano del banco: en `ejemplo.dxf` las tres celdas de
    total están vacías. Lo dispara el plano de un arquitecto con la memoria ya
    redactada. El arreglo es enrutar los tres totales por el mismo
    `_con_conflicto_o` que ya usa `aplicar_respuestas` más abajo."""
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
    presentes = [c for c in componentes if c.estado != NO_DIBUJADA]
    if not presentes:
        return CeldaRelleno(
            campo, "", NO_DIBUJADA,
            "%s no se escribe: el plano no dibuja ninguna estancia de este lado, y un "
            "total de 0,00 m² no es una superficie (D-13)." % etiqueta_total,
            celda, escribir=False)
    valores = [(c, _valor_numerico(c)) for c in presentes]
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


def superficie_en_m2(texto: Optional[str]) -> Optional[float]:
    """El número de un texto de celda, solo si está en el formato exacto que
    genera `_formatear_area` ("21,90 m²"). `None` -- nunca una conversión
    aproximada -- si no lo está.

    Público porque lo necesita más de un consumidor: además del cálculo del
    total (`_celda_total`), la verificación de la Skill que cruza el cuadro
    contra la superficie medida (`agente/skills/superficies.py`). Tenían dos
    parseos distintos y el de la Skill era más laxo: aceptaba "8" (el
    `NUMERO UDS` de `ejemplo.dxf`) como si fueran 8 m². Uno solo, y el
    estricto.

    **Un texto que no case es «no sumable con garantías», nunca 0.** Típicamente
    una celda PREEXISTENTE que escribió un humano en otro formato ("21.90m2",
    como en `ejemplo.dxf`). Quien llame debe declararlo, no saltárselo: una
    suma a la que le falta un sumando en silencio es peor que no sumar.
    """
    if not texto:
        return None
    m = re.fullmatch(r"(\d+),(\d{2}) m²", texto.strip())
    if not m:
        return None
    return float(m.group(1) + "." + m.group(2))


def _valor_numerico(celda_rellena: CeldaRelleno) -> Optional[float]:
    """`superficie_en_m2` sobre el texto de una celda ya resuelta."""
    return superficie_en_m2(celda_rellena.texto)


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
    componentes_interior = [por_campo[c] for c in CAMPOS_UTIL_INTERIOR]
    total_interior = _celda_total("total_util_interior", cuadro.celda("total_util_interior"),
                                   componentes_interior, "TOTAL SUP.UTIL INTERIOR")
    resultados.append(total_interior)
    por_campo["total_util_interior"] = total_interior

    componentes_exterior = [por_campo[c] for c in CAMPOS_UTIL_EXTERIOR]
    total_exterior = _celda_total("total_util_exterior", cuadro.celda("total_util_exterior"),
                                   componentes_exterior, "TOTAL SUP.UTIL EXTERIOR")
    resultados.append(total_exterior)
    por_campo["total_util_exterior"] = total_exterior

    # "TOTAL S. ÚTIL" -- **ya no se calcula**. Ver `MOTIVO_TOTAL_UTIL_NO_SE_SUMA`:
    # el encargo original pedía interior + exterior en una celda, y el criterio
    # firmado del 2026-09-07 lo deroga. No se suma aquí ni en ningún otro sitio.
    resultados.append(_total_util_no_se_suma(cuadro.celda("total_util")))

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

    return guardian_d13(resultados)


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

#: Cómo se llama cada campo cuando **lo escribe ArchMuse**, no el arquitecto.
#:
#: Se usa en dos sitios y conviene saber que son distintos: al preguntarle por
#: una celda que no ha podido resolver, y al dibujar el cuadro canónico de
#: `plantilla_canonica()`. Cuando hay cuadro en el plano **esto no se usa**: se
#: copian sus etiquetas, que son las suyas.
_ETIQUETA_CAMPO = {
    "salon_cocina": "Salón + cocina",
    "pasillo": "Pasillo",
    "dormitorio_1": "Dormitorio 1",
    "dormitorio_2": "Dormitorio 2",
    "dormitorio_3": "Dormitorio 3",
    "bano": "Baño",
    "aseo": "Aseo",
    "vestibulo": "Vestíbulo",
    "tendedero": "Tendedero", "terraza_1": "Terraza 1", "terraza_2": "Terraza 2",
    "total_util_interior": "TOTAL SUP. ÚTIL INTERIOR (m2)",
    "total_util_exterior": "TOTAL SUP. ÚTIL EXTERIOR (m2)",
    "total_util": "TOTAL S. ÚTIL (m2)",
    "superficie_construida_cerrada": "Superficie construida cerrada",
    "superficie_construida_exterior": "Superficie construida exterior",
    "numero_unidades": "Número de unidades",
    "vivienda_tipo": "VIVIENDA TIPO",
}

#: Las filas del cuadro canónico, en orden, y en qué lado van. `True` = columna
#: izquierda (interiores y totales), `False` = derecha (exteriores).
#:
#: **El orden no es libre: es el de sus cuadros.** Interiores arriba a la
#: izquierda, exteriores arriba a la derecha, totales debajo. Se ha copiado la
#: disposición de los tres cuadros del estudio porque es la única referencia que
#: hay de cómo se lee un cuadro de superficies en este despacho.
_ORDEN_CANONICO = (
    ("salon_cocina", True), ("pasillo", True),
    ("dormitorio_1", True), ("dormitorio_2", True), ("dormitorio_3", True),
    ("bano", True), ("aseo", True), ("vestibulo", True),
    ("tendedero", False), ("terraza_1", False), ("terraza_2", False),
    ("total_util_interior", True), ("total_util_exterior", False),
    ("total_util", True),
    ("superficie_construida_cerrada", True),
    ("superficie_construida_exterior", True),
    ("numero_unidades", False), ("vivienda_tipo", True),
)

#: Encabezados del cuadro canónico: (fila, columna, texto).
_ENCABEZADOS_CANONICOS = (
    (0, 0, "ESPACIOS INTERIORES"), (0, 1, "SUPERFICIES ÚTILES"),
    (0, 2, "ESPACIOS EXTERIORES"), (0, 3, "SUPERFICIES ÚTILES"),
)


def plantilla_canonica() -> CuadroSuperficies:
    """El cuadro que ArchMuse dibuja cuando **el plano no trae ninguno**.

    ### Por qué esto puede existir sin elegir por el arquitecto

    El PRD del 2026-09-11 se frenó en parte porque **no existe «el formato del
    estudio»**: sus tres cuadros tienen 17, 18 y 18 campos y escriben la misma
    fila de tres maneras (`S. CONSTRUIDA C.`, `S. CONSTRUIDA CERRADA`,
    `S. CONSTRUIDA CERRADA.`). Copiar uno era elegir por él cuál de sus tres
    formatos es el bueno, que es el tipo de decisión que `C-1`, `C-2` y `C-8`
    dicen que ArchMuse no toma.

    **Con el diseño del 2026-09-12 esa objeción se cae en los casos B, C y D**:
    no se elige formato, se copia el que hay delante. Sobrevive sólo aquí,
    cuando no hay ninguno, y se resuelve **declarándolo**: la tabla dice
    «ArchMuse · BORRADOR» y usa `CAMPOS_DEL_CUADRO`, que es **el formato de
    ArchMuse**. No se le atribuye a él un formato que no ha elegido, y por eso
    deja de ser una decisión tomada en su nombre.

    Las celdas no llevan coordenadas de dibujo (`x=0, y=0`): aquí no hay tabla
    que leer, y el punto de inserción lo pone el arquitecto con el ratón.
    """
    celdas: List[CeldaCuadro] = []
    filas: List[FilaDeCuadro] = []

    for f, c, texto in _ENCABEZADOS_CANONICOS:
        filas.append(FilaDeCuadro(fila=f, etiqueta=texto, campo=None,
                                  columna_etiqueta=c, columna_valor=c))

    siguiente = {True: 1, False: 1}
    for campo, izquierda in _ORDEN_CANONICO:
        col_etiqueta = 0 if izquierda else 2
        fila = siguiente[izquierda]
        siguiente[izquierda] += 1
        filas.append(FilaDeCuadro(
            fila=fila, etiqueta=_ETIQUETA_CAMPO[campo], campo=campo,
            columna_etiqueta=col_etiqueta, columna_valor=col_etiqueta + 1))
        celdas.append(CeldaCuadro(
            campo=campo, etiqueta=_ETIQUETA_CAMPO[campo],
            columna="B" if col_etiqueta == 0 else "D",
            x=0.0, y=0.0, texto_actual=None,
            fila=fila, columna_indice=col_etiqueta + 1,
            columna_etiqueta=col_etiqueta))

    filas.sort(key=lambda x: (x.fila, x.columna_etiqueta))
    return CuadroSuperficies(celdas=celdas, etiquetas_sin_campo=(),
                             filas=tuple(filas))


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
                    # El arquitecto confirma que no hay pieza real para este
                    # hueco. Hasta el 2026-09-13 eso escribía un `0,00 m²`
                    # «declarado»; con `D-13` una estancia que no existe no mide
                    # cero, ni aunque lo confirme él: la celda queda vacía y el
                    # motivo dice que lo ha confirmado.
                    por_campo[campo] = _con_conflicto_o(
                        campo, "",
                        lambda campo=campo, celda_destino=celda_destino: CeldaRelleno(
                            campo, "", NO_DIBUJADA,
                            "El arquitecto confirma que no hay ninguna pieza real para este "
                            "hueco. No se escribe 0,00 m² (D-13).",
                            celda_destino, escribir=False, declarado_por_usuario=True,
                        ),
                    )
        else:
            raise ValueError("tipo de respuesta desconocido: %r" % tipo)

    # Recalcular los totales en cascada, con la MISMA función que los
    # calculó la primera vez -- ninguna fórmula nueva.
    componentes_interior = [por_campo[c] for c in CAMPOS_UTIL_INTERIOR]
    total_interior = _celda_total("total_util_interior", por_campo["total_util_interior"].celda,
                                   componentes_interior, "TOTAL SUP.UTIL INTERIOR")
    por_campo["total_util_interior"] = total_interior

    componentes_exterior = [por_campo[c] for c in CAMPOS_UTIL_EXTERIOR]
    total_exterior = _celda_total("total_util_exterior", por_campo["total_util_exterior"].celda,
                                   componentes_exterior, "TOTAL SUP.UTIL EXTERIOR")
    por_campo["total_util_exterior"] = total_exterior

    # Ninguna respuesta del arquitecto reabre esta celda: no es un dato que le
    # falte a ArchMuse, es una magnitud que ArchMuse ha decidido no componer.
    por_campo["total_util"] = _total_util_no_se_suma(por_campo["total_util"].celda)

    # Mismo orden que `resultados` de entrada, para que la salida sea estable.
    return guardian_d13([por_campo[r.campo] for r in resultados])


# ---------------------------------------------------------------------------
# Detección (IMPURA -- lee ezdxf). Separada a propósito de
# `calcular_relleno_cuadro`: esta función construye el `CuadroSuperficies`
# de entrada a partir de un DXF real; `calcular_relleno_cuadro` nunca sabe
# que ezdxf existe. Implementa el hallazgo de la Fase 1: el cuadro es un
# `ACAD_TABLE` cuyo título identifica la tabla sin depender de coordenadas
# fijas -- las coordenadas se leen de la rejilla de LINE de cada archivo.
# ---------------------------------------------------------------------------

TITULO_CUADRO = "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"

# El diccionario de cadenas exactas que vivía aquí se retiró el 2026-09-10.
# Reconocía 13 de 17 campos del segundo cuadro del mismo arquitecto —fallaba por
# un espacio, un punto y una abreviatura— y su docstring ya avisaba de que otra
# redacción «exigiría ampliar esta tabla». Ampliarla plano a plano era el
# camino a una capacidad que hay que parchear por cliente.
#
# Lo sustituye `emparejador_cuadro.emparejar`, que empareja por palabras
# presentes y **empareja todas las etiquetas a la vez**, para poder ver que dos
# filas pidan el mismo campo.



# ---------------------------------------------------------------------------
# `D-13` · Ninguna celda de superficie dice `0,00 m²`. Deroga `C-4`.
# ---------------------------------------------------------------------------
#
# **`C-4` (2026-09-10) decía que un cero se escribía sobre una medición limpia.**
# Se aplicaba sólo en la vía del comando (`D-15`: la web nunca pasó por él), y
# sobre medición limpia dejaba pasar justo el caso que Pablo vio en AutoCAD el
# 2026-09-13: filas `pasillo` y `vestibulo` que el plano no dibuja. `D-13` lo
# sustituye por algo más simple y más fuerte: **ninguna habitación mide cero**.
#
# **Por qué el guardián no se calla.** Si algún día un cálculo vuelve a producir
# un cero, esta función no lo convierte en silencio en una celda vacía —eso
# taparía el fallo y los tests seguirían verdes—: lo convierte en una celda vacía
# con `MOTIVO_GUARDIAN_D13`, que dice que es un fallo de ArchMuse. Los tests
# buscan ese motivo. El arquitecto no ve un cero; el repositorio ve un rojo.

#: Lo que lleva una celda en la que ArchMuse **iba** a escribir un cero. Si
#: aparece en algún sitio, hay un productor de ceros nuevo que buscar.
MOTIVO_GUARDIAN_D13 = (
    "ArchMuse iba a escribir 0,00 m² en esta celda y el guardián de D-13 lo ha "
    "impedido. Es un fallo de ArchMuse, no de tu plano: la celda se queda vacía."
)


def es_superficie_cero(texto: Optional[str]) -> bool:
    """`True` para `0,00 m²` y sus variantes (`0.00m2`, `0 m²`)."""
    return bool(re.search(r"(?<![\d.,])0+(?:[.,]0+)?\s*m", texto or "", re.IGNORECASE))


def guardian_d13(celdas: Sequence[CeldaRelleno]) -> List[CeldaRelleno]:
    """`D-13` sobre la salida: ninguna celda sale con una superficie cero."""
    resultado: List[CeldaRelleno] = []
    for c in celdas:
        if es_superficie_cero(c.texto) and not c.preexistente:
            resultado.append(CeldaRelleno(
                c.campo, "", BLOQUEADO, MOTIVO_GUARDIAN_D13, c.celda,
                escribir=False, declarado_por_usuario=c.declarado_por_usuario))
        else:
            resultado.append(c)
    return resultado


#: Familia -> campo del cuadro. Es el mismo vocabulario de `FAMILIAS` en
#: `medicion.py`, que importa estos patrones de aquí: una sola definición de qué
#: es un tendedero, tanto para medir como para repartir.
_PATRON_A_CAMPO = (
    (_PATRON_SALON_COCINA, "salon_cocina"),
    (_PATRON_PASILLO, "pasillo"),
    (_PATRON_VESTIBULO, "vestibulo"),
    (_PATRON_BANO, "bano"),
    (_PATRON_ASEO, "aseo"),
    (_PATRON_TENDEDERO, "tendedero"),
)


def campo_de_la_pieza(rotulo: str) -> Optional[str]:
    """En qué fila del cuadro va una pieza medida, por su rótulo.

    Devuelve `None` cuando el rótulo no es de ninguna familia conocida — y eso
    **no se descarta en silencio**: quien llama lo declara como pieza sin fila
    (`C-6`). Los dormitorios y las terrazas llevan número, así que se resuelven
    aparte: «Dormitorio 2» va a `dormitorio_2`, no a un `dormitorio` genérico.
    """
    normalizado = _normalizar(rotulo or "")
    if not normalizado.strip():
        return None
    for n in (1, 2, 3):
        if _patron_dormitorio(n).search(normalizado):
            return "dormitorio_%d" % n
    if _PATRON_TERRAZA.search(normalizado):
        numero = re.search(r"\b([12])\b", normalizado)
        return "terraza_%s" % (numero.group(1) if numero else "1")
    for patron, campo in _PATRON_A_CAMPO:
        if patron.search(normalizado):
            return campo
    return None



def cuadro_desde_celdas(celdas: Sequence[Sequence]) -> Optional[CuadroSuperficies]:
    """El cuadro construido a partir de las celdas que manda el cliente CAD.

    `celdas` son tripletas `(fila, columna, texto)` leídas de la tabla del
    arquitecto con la API de AutoCAD. Es la otra forma de llegar al mismo
    `CuadroSuperficies` que `detectar_cuadro_superficies` obtiene de un DXF, y
    existe porque **desde AutoCAD no hace falta reconstruir la rejilla**: la
    tabla ya dice en qué fila y en qué columna está cada cosa. Lo que se evita
    con eso es tener dos maneras de decidir qué fila es cada etiqueta; la
    decisión sigue siendo una sola, la de `emparejar`.

    Convención de columnas, la misma de siempre: las pares (0, 2) llevan las
    etiquetas y las impares (1, 3) los valores. Una etiqueta de la columna 0
    tiene su valor en la 1; una de la 2, en la 3.

    Devuelve `None` si no hay ninguna etiqueta reconocible, que es como decir
    «esto no es un cuadro de superficies»; nunca un cuadro vacío que luego
    parezca que no tenía filas.
    """
    # **Qué celda es una etiqueta lo decide el emparejador, no su posición.**
    # Antes se clasificaba por paridad —pares etiqueta, impares valor—, que es
    # como son los tres cuadros de este estudio y nada más lo garantizaba. Un
    # cuadro con otra disposición no fallaba: escribía las cifras correctas en la
    # columna equivocada. Ahora se prueba cada celda contra el vocabulario y la
    # que reclama un campo es la etiqueta, esté donde esté.
    todas = []
    for celda in celdas:
        try:
            fila, columna, texto = int(celda[0]), int(celda[1]), str(celda[2] or "")
        except (TypeError, ValueError, IndexError):
            continue
        todas.append((fila, columna, texto))

    ultima_columna = max((c for _f, c, _t in todas), default=-1)
    valores: Dict[tuple, str] = {(f, c): t for f, c, t in todas}

    candidatas = [(f, c, t) for f, c, t in todas if t.strip()]
    emparejadas = emparejar([texto for _f, _c, texto in candidatas])

    resultado: List[CeldaCuadro] = []
    sin_campo: List[tuple] = []
    filas_literales: List[FilaDeCuadro] = []
    for (fila, columna, texto), pareja in zip(candidatas, emparejadas, strict=True):
        if pareja.campo is None:
            if pareja.motivo:
                sin_campo.append((texto, pareja.motivo))
            filas_literales.append(FilaDeCuadro(
                fila=fila, etiqueta=texto, campo=None, motivo=pareja.motivo,
                columna_etiqueta=columna,
                columna_valor=min(columna + 1, ultima_columna)))
            continue
        # **La celda a rellenar es la de la derecha de su etiqueta**, sea cual
        # sea su índice. Si la etiqueta está en la última columna no hay ninguna,
        # y eso se declara en vez de escribir en otro sitio.
        col_valor = columna + 1
        if col_valor > ultima_columna:
            motivo_borde = (
                "la fila «%s» tiene su etiqueta en la última columna del cuadro "
                "(la %d): no hay ninguna celda a su derecha donde escribir la "
                "cifra" % (texto, columna))
            sin_campo.append((texto, motivo_borde))
            filas_literales.append(FilaDeCuadro(
                fila=fila, etiqueta=texto, campo=None, motivo=motivo_borde,
                columna_etiqueta=columna, columna_valor=columna))
            continue
        actual = valores.get((fila, col_valor)) or None
        resultado.append(CeldaCuadro(
            campo=pareja.campo, etiqueta=texto,
            columna="B" if col_valor == 1 else "D",
            fila=fila, columna_indice=col_valor, columna_etiqueta=columna,
            # Sin coordenadas: por esta vía escribe AutoCAD en la celda, no un
            # MTEXT superpuesto, así que el punto no hace falta y poner un cero
            # es más honesto que inventarse una posición.
            x=0.0, y=0.0,
            texto_actual=actual,
        ))
        filas_literales.append(FilaDeCuadro(
            fila=fila, etiqueta=texto, campo=pareja.campo,
            columna_etiqueta=columna, columna_valor=col_valor))
    # **«No hay cuadro» y «hay cuadro y no se puede rellenar» son distintos.**
    # Si no se ha reconocido NINGUNA etiqueta, esto no es un cuadro de
    # superficies y se dice que no hay. Pero si se reconocieron y aun así no
    # queda ninguna celda escribible —todas con su etiqueta en la última
    # columna, por ejemplo— el cuadro **sí existe** y devolver `None` haría que
    # el arquitecto leyera «no se reconoce ningún cuadro», que es falso y le
    # manda a mirar donde no es. Se devuelve con cero celdas y con los motivos
    # puestos, que es lo que de verdad pasa.
    if not resultado and not sin_campo:
        return None

    # Mismo filtro que al leer el DXF: **una celda de valor suya no es una fila
    # de su cuadro**. Sin esto, el cuadro que ArchMuse dibuja al lado sale con
    # las cifras del arquitecto dentro, presentadas como medidas por él.
    posiciones_de_valor = {(c.fila, c.columna_indice) for c in resultado}
    filas_literales = [
        f for f in filas_literales
        if f.campo is not None
        or (f.fila, f.columna_etiqueta) not in posiciones_de_valor
    ]
    filas_literales.sort(key=lambda f: (f.fila, f.columna_etiqueta))

    return CuadroSuperficies(celdas=tuple(resultado),
                             etiquetas_sin_campo=tuple(sin_campo),
                             filas=tuple(filas_literales))


def detectar_cuadro_superficies(doc) -> Optional[CuadroSuperficies]:
    """Busca el `ACAD_TABLE` "CUADRO DE SUPERFICIES..." en `doc` (un
    `ezdxf.document.Drawing` ya cargado) y devuelve su `CuadroSuperficies`,
    o `None` si no se encuentra ninguno con ese título.

    Detección por **encabezado**, no por coordenadas fijas (Fase 1, punto 6):
    cualquier `ACAD_TABLE` de `doc.modelspace()` cuyo primer MTEXT normalizado
    sea `TITULO_CUADRO` se acepta; la rejilla de celdas se reconstruye en cada
    caso a partir de las LINE de ESE `ACAD_TABLE`, no de una tabla fija.

    ### LÍMITE: devuelve **el primero**, y un proyecto real tiene varios

    Este `return` dentro del bucle no es una optimización: es el techo de lo que
    ArchMuse sabe ver por esta vía. **`plantasimple.dxf` tiene 25 cuadros**, uno
    por vivienda, y es el único proyecto completo del lote —así que varios
    cuadros no son la rareza, son la forma normal de un proyecto de verdad
    (medido el 2026-09-12, `docs/PROGRESS.md`)—.

    Por la vía del comando el límite no se nota, porque el cliente CAD manda las
    celdas del cuadro que el arquitecto ha elegido y el servidor reparte **ese**.

    Por la vía web no es una pérdida muda —`coherencia.revisar` mete el contraste
    en `no_comprobado` en cuanto el plano tiene más de una vivienda— pero **sí
    está mal nombrada**: lo que dice es *«un cuadro describe una sola vivienda»*,
    y en `plantasimple.dxf` lo cierto es que **hay 25 cuadros y se ha leído 1**.
    El arquitecto lee que no se puede contrastar por culpa de su plano, cuando el
    motivo real es el techo de esta función. Un motivo que señala al sitio
    equivocado manda la búsqueda al sitio equivocado, que es lo que ya costó una
    sesión con el recuento de polilíneas de `v1plantas.dxf`.

    Mientras esto siga así, **no vale recorrer las tablas desde fuera** —ni desde
    un test, ni desde un script—: sería una segunda implementación del criterio
    de detección fuera de este módulo, que es lo que prohibe `D-7`. El barrido,
    cuando haga falta, se escribe **aquí**.
    """
    cuadros = detectar_cuadros_superficies(doc)
    return cuadros[0] if cuadros else None


def detectar_cuadros_superficies(doc) -> List[CuadroSuperficies]:
    """**Todos** los cuadros del plano, en el orden en que están en el dibujo.

    ### Por qué el plural no es una comodidad

    `plantasimple.dxf` —el único proyecto completo del lote— tiene **25 cuadros**,
    uno por vivienda. Con el detector en singular, ArchMuse leía **uno** y los 24
    restantes no existían para el producto: `coherencia` acababa diciendo que no
    podía contrastar *«porque un cuadro describe una sola vivienda»*, que es
    verdad y **no era el motivo**. Un motivo que señala al sitio equivocado manda
    la búsqueda al sitio equivocado.

    Varios cuadros por plano no es un caso límite: es la forma normal de un
    proyecto de verdad. Medido el 2026-09-12; PRD `2026-09-12`, §10.

    Un cuadro cuya rejilla no se pueda reconstruir **no tumba a los demás**: se
    salta. Un plano de 25 cuadros donde el tercero venga raro tiene que seguir
    dando 24, no cero.
    """
    cuadros: List[CuadroSuperficies] = []
    for tabla in doc.modelspace().query("ACAD_TABLE"):
        try:
            entidades = list(tabla.virtual_entities())
        except Exception:  # noqa: BLE001 - tabla de un cliente ajeno
            continue
        mtexts = [e for e in entidades if e.dxftype() == "MTEXT"]
        lines = [e for e in entidades if e.dxftype() == "LINE"]
        if not any(_normalizar(m.text) == TITULO_CUADRO for m in mtexts):
            continue
        try:
            cuadros.append(_construir_cuadro(mtexts, lines))
        except ValueError:
            # `_construir_cuadro` se niega si la rejilla no tiene 4 columnas.
            # Negarse es correcto; contagiar la negativa a los otros 24, no.
            continue
    return cuadros


def cajas_y_alturas_de_los_cuadros(doc):
    """`(cajas, alturas)` de los cuadros de superficies del plano (vía web).

    **Para qué, desde el 2026-09-13.** Con la plantilla fija el cuadro del
    arquitecto ya no aporta filas: sólo dice **dónde no dibujar** (sus cajas) y
    **por debajo de qué altura de texto no se escribe** (la menor de sus celdas,
    `D-14`). El cliente CAD manda lo mismo leído de la tabla viva.

    Vive aquí y no en quien lo usa por la regla del docstring de
    `detectar_cuadro_superficies`: qué tabla es un cuadro se decide en este
    módulo, en un solo sitio.
    """
    cajas, alturas = [], []
    for tabla in doc.modelspace().query("ACAD_TABLE"):
        try:
            entidades = list(tabla.virtual_entities())
        except Exception:  # noqa: BLE001 - tabla de un cliente ajeno
            continue
        mtexts = [e for e in entidades if e.dxftype() == "MTEXT"]
        if not any(_normalizar(m.text) == TITULO_CUADRO for m in mtexts):
            continue
        xs = [v for e in entidades if e.dxftype() == "LINE" for v in (e.dxf.start.x, e.dxf.end.x)]
        ys = [v for e in entidades if e.dxftype() == "LINE" for v in (e.dxf.start.y, e.dxf.end.y)]
        if xs and ys:
            cajas.append(((min(xs), min(ys)), (max(xs), max(ys))))
        alturas.extend(float(m.dxf.char_height) for m in mtexts
                       if m.dxf.get("char_height"))
    return cajas, alturas


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

    # Igual que en `cuadro_desde_celdas`: **la etiqueta la decide el
    # emparejador, no la paridad de su columna**. Aquí se recogen todos los
    # textos con su celda y se prueba después cuáles reclaman un campo.
    etiquetas = []
    valores_existentes: Dict[tuple, str] = {}
    ultima_columna = len(col_centro) - 1
    for m in mtexts:
        ip = m.dxf.insert
        col = _banda(ip.x, xs)
        fila = _banda(ip.y, ys)
        if col < 0 or fila < 0:
            continue
        valores_existentes[(fila, col)] = m.text
        etiquetas.append((fila, col, m.text, ip.x, ip.y))

    # Las etiquetas se emparejan TODAS A LA VEZ, no una a una: de una en una no
    # se puede ver que dos filas distintas pidan el mismo campo, que es la
    # ambigüedad que hace daño de verdad (ver `emparejador_cuadro.emparejar`).
    emparejadas = emparejar([texto for _f, _c, texto, _x, _y in etiquetas])

    celdas = []
    sin_campo = []
    # Todas las filas, reconocidas o no, para poder **copiar su cuadro** al
    # dibujar el de ArchMuse al lado. Ver `FilaDeCuadro`.
    filas_literales = []
    # `strict=True`: `emparejar` devuelve un resultado por etiqueta, siempre. Si
    # algún día dejara de hacerlo, truncar en silencio dejaría filas del cuadro
    # sin emparejar sin que nadie se enterara — que es justo lo que `C-6` no
    # permite.
    for (fila, col_etiqueta, texto_etiqueta, _lx, ly), pareja in zip(
            etiquetas, emparejadas, strict=True):
        if pareja.campo is None:
            # Un encabezado de grupo («ESPACIOS EXTERIORES») o el título no son
            # una fila y no llevan motivo. Una fila que sí lo parecía y no se ha
            # podido resolver, sí: se guarda para poder decirlo.
            if pareja.motivo:
                sin_campo.append((texto_etiqueta, pareja.motivo))
            # Va a las filas literales **igual**: el título y los encabezados son
            # parte de su tabla, y copiarla sin ellos desalinearía la
            # comparación, que es justo para lo que existe.
            filas_literales.append(FilaDeCuadro(
                fila=fila, etiqueta=texto_etiqueta, campo=None,
                motivo=pareja.motivo, columna_etiqueta=col_etiqueta,
                columna_valor=min(col_etiqueta + 1, ultima_columna)))
            continue
        # La celda de la derecha de su etiqueta, sea cual sea su índice.
        col_valor = col_etiqueta + 1
        if col_valor > ultima_columna:
            motivo_borde = (
                "la fila «%s» tiene su etiqueta en la última columna del cuadro "
                "(la %d): no hay ninguna celda a su derecha donde escribir la "
                "cifra" % (texto_etiqueta, col_etiqueta))
            sin_campo.append((texto_etiqueta, motivo_borde))
            filas_literales.append(FilaDeCuadro(
                fila=fila, etiqueta=texto_etiqueta, campo=None,
                motivo=motivo_borde, columna_etiqueta=col_etiqueta,
                columna_valor=col_etiqueta))
            continue
        texto_actual = valores_existentes.get((fila, col_valor))
        celdas.append(CeldaCuadro(
            campo=pareja.campo,
            etiqueta=texto_etiqueta,
            columna="B" if col_valor == 1 else "D",
            fila=fila,
            columna_indice=col_valor,
            columna_etiqueta=col_etiqueta,
            x=col_centro[col_valor],
            y=ly,
            texto_actual=texto_actual,
        ))
        filas_literales.append(FilaDeCuadro(
            fila=fila, etiqueta=texto_etiqueta, campo=pareja.campo,
            columna_etiqueta=col_etiqueta, columna_valor=col_valor))

    # **Sus cifras no son filas de su cuadro, y esto es lo que lo impide.**
    #
    # `etiquetas` (arriba) contiene TODOS los MTEXT de la rejilla, y una celda de
    # valor —«23.85m²»— es un MTEXT como cualquier otro: no casa con ningún
    # campo, así que llega aquí indistinguible de un encabezado de grupo. Sin
    # este filtro, **el cuadro que ArchMuse dibuja al lado sale con las cifras
    # del arquitecto dentro**, presentadas como suyas. Es el peor fallo posible
    # de esta capacidad: no es que falte un dato, es que ArchMuse firma un
    # número que no ha medido.
    #
    # Se filtra por posición y no por aspecto: una celda es de valor cuando es
    # **la celda de valor de un campo que sí se ha reconocido**, no cuando su
    # texto se parece a una superficie. Un encabezado que viva en una columna de
    # valor —«SUPERFICIES UTILES», que es el caso de estos cuadros— no está en
    # ninguna fila con campo y **sobrevive**, que es lo que tiene que pasar.
    posiciones_de_valor = {(c.fila, c.columna_indice) for c in celdas}
    filas_literales = [
        f for f in filas_literales
        if f.campo is not None
        or (f.fila, f.columna_etiqueta) not in posiciones_de_valor
    ]

    # Por fila y, dentro de la fila, por columna: es como se dibuja. Ni el
    # recorrido de MTEXT ni el de `virtual_entities` lo garantizan.
    filas_literales.sort(key=lambda f: (f.fila, f.columna_etiqueta))
    return CuadroSuperficies(celdas=celdas, etiquetas_sin_campo=tuple(sin_campo),
                             filas=tuple(filas_literales))
