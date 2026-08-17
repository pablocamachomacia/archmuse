# -*- coding: utf-8 -*-
"""Detección de la escala de un DXF: en qué unidad está dibujado el plano.

Tarea 3 del PRD `docs/prd/2026-08-02-ingesta-de-dxf-ajenos.md`.

**Por qué existe este módulo.** Hasta ahora `parser.Room.area_m2` devolvía
`polygon.area` con el comentario «se asume metros», y nadie leía `$INSUNITS`
en todo el proyecto. Un DXF dibujado en milímetros —práctica corriente en
España— entraba con cada área multiplicada por 1.000.000 y *no fallaba*: todas
las superficies mínimas se cumplían holgadamente, el plano se dibujaba perfecto
porque `plan_svg` normaliza al `viewBox`, y el proyecto salía con una
puntuación alta y creíble. El sistema no se rompía: mentía con confianza.

**Las dos fuentes, y por qué hacen falta las dos.** `$INSUNITS` es la respuesta
oficial del archivo, pero está a 0 («sin especificar») con muchísima frecuencia
y a veces está sencillamente mal — una plantilla heredada que nadie corrigió.
Así que la cabecera sola no basta. La segunda fuente es el tamaño de lo
dibujado: una habitación de vivienda mide lo que mide, y eso permite descartar
órdenes de magnitud absurdos sin creerse nada de lo que declare el archivo.

**La regla que gobierna el módulo:** cuando las dos fuentes no se ponen de
acuerdo, o cuando ninguna decide, `EscalaDetectada.factor` queda a `None` y hay
que preguntar al arquitecto. No se adivina en silencio nunca. Es lo que exige
`NORTH_STAR_2031.md` como principio no negociable: *nunca se muestra un dato
como real si no lo es*.

Este módulo no aplica la escala a nada — solo la determina. Aplicarla al
pipeline es la tarea 4 del PRD.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

# Códigos de `$INSUNITS` según la especificación DXF, restringidos a los que
# tienen sentido en un plano de arquitectura, con su factor de conversión a
# metros. Cualquier otro código se trata como no utilizable (ver
# `NO_METRICOS` y `_UNIDAD_DESCONOCIDA`).
UNIDADES_METRICAS = {
    4: ("milímetros", 0.001),
    5: ("centímetros", 0.01),
    6: ("metros", 1.0),
    14: ("decímetros", 0.1),
}

# Códigos imperiales. Se rechazan explícitamente en vez de convertirlos: el
# motor de reglas entero está escrito contra el CTE, en métrico y para España.
# Convertir un plano en pies daría números correctos bajo una normativa que no
# es la suya, que es una forma peor de estar equivocado que negarse.
NO_METRICOS = {
    1: "pulgadas",
    2: "pies",
    3: "millas",
    8: "micropulgadas",
    9: "mils",
    10: "yardas",
}

# Orden de preferencia al informar de varias hipótesis compatibles: de la
# unidad de dibujo más habitual en arquitectura a la menos.
ORDEN_HIPOTESIS = ["metros", "milímetros", "centímetros", "decímetros"]

# Rango, en m², dentro del cual el área de una estancia de vivienda es
# plausible. Un aseo baja de 3 m² y un salón-cocina-comedor de una vivienda
# grande pasa de 60, así que el rango es deliberadamente ancho: sirve para
# descartar órdenes de magnitud absurdos (0,00002 m² o 24.000.000 m²), no para
# validar una habitación concreta.
#
# El ancho tiene un techo que no se puede rebasar: entre dos unidades vecinas
# (metros/decímetros, centímetros/milímetros) hay un factor de 100 en área, así
# que mientras el rango abarque menos de 100x es imposible que dos hipótesis
# salgan compatibles a la vez. 150/2 = 75x deja margen y conserva esa garantía
# —que `tests/test_escala.py` comprueba explícitamente—.
AREA_PLAUSIBLE_MIN_M2 = 2.0
AREA_PLAUSIBLE_MAX_M2 = 150.0

# Por debajo de esta cantidad de estancias, la mediana no es un estadístico
# fiable y la plausibilidad no se usa como fuente de decisión (aunque sí se
# informa). Un DXF con dos polígonos puede ser cualquier cosa.
MINIMO_ESTANCIAS_PARA_PLAUSIBILIDAD = 3


@dataclass
class EscalaDetectada:
    """Resultado de la detección.

    `factor` es el multiplicador de **longitud** a metros. Para convertir un
    área hay que elevarlo al cuadrado — usar `factor_area` y no multiplicar a
    mano, que confundir los dos es exactamente el error que este módulo
    existe para evitar.

    `factor` vale `None` cuando ArchMuse no puede decidir por su cuenta. En ese
    caso `sugerencia` lleva la mejor conjetura, para ofrecerla al arquitecto ya
    marcada en la pantalla de confirmación, pero el pipeline **no** puede
    usarla sin que alguien la confirme.
    """

    factor: Optional[float]
    unidad: str
    origen: str  # "acuerdo" | "cabecera" | "plausibilidad" | "conflicto" | "indecidible" | "no_metrico"
    mensaje: str
    codigo_insunits: int = 0
    unidad_cabecera: str = ""
    hipotesis_por_tamano: List[str] = field(default_factory=list)
    sugerencia: Optional[str] = None
    area_mediana_dibujo: float = 0.0

    @property
    def decidida(self) -> bool:
        """`True` si ArchMuse puede seguir sin preguntar."""
        return self.factor is not None

    @property
    def factor_area(self) -> Optional[float]:
        """Multiplicador para pasar un área de unidades de dibujo a m²."""
        return None if self.factor is None else self.factor * self.factor


def factor_de_unidad(nombre: str) -> Optional[float]:
    """Factor de longitud a metros de una unidad nombrada en español, o `None`
    si no se reconoce. Es la vía por la que entra la respuesta del arquitecto
    en la pantalla de confirmación."""
    for _codigo, (nombre_unidad, factor) in UNIDADES_METRICAS.items():
        if nombre_unidad == nombre:
            return factor
    return None


def unidad_de_factor(factor: float) -> str:
    """Nombre de la unidad cuyo factor de longitud es `factor`, o "" si no se
    corresponde con ninguna conocida."""
    for nombre_unidad, valor in UNIDADES_METRICAS.values():
        if abs(valor - factor) < 1e-12:
            return nombre_unidad
    return ""


def escala_confirmada(factor: float) -> "EscalaDetectada":
    """La escala que ha confirmado el arquitecto. Séptimo desenlace, y el único
    que no deduce nada: alguien miró el plano y lo dijo.

    Existe para que el resto del sistema pueda tratar todos los casos con el
    mismo objeto y no haya un camino paralelo, sin `origen` ni `mensaje`, por
    el que se cuele un factor sin trazabilidad.
    """
    unidad = unidad_de_factor(factor)
    return EscalaDetectada(
        factor=factor,
        unidad=unidad,
        origen="confirmada",
        unidad_cabecera="",
        mensaje="Escala indicada por el arquitecto: %s." % (unidad or "factor %g" % factor),
    )


def leer_insunits(doc) -> int:
    """Código `$INSUNITS` de la cabecera del DXF, o 0 si falta o es ilegible.

    Único punto del módulo que toca ezdxf; todo lo demás son funciones puras
    sobre números, para poder probarlas sin fabricar un DXF.
    """
    try:
        return int(doc.header.get("$INSUNITS", 0) or 0)
    except Exception:  # noqa: BLE001 - cabecera de un DXF ajeno: puede venir con cualquier cosa
        return 0


def _mediana(valores: Sequence[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    n = len(ordenados)
    if n % 2:
        return ordenados[n // 2]
    return (ordenados[n // 2 - 1] + ordenados[n // 2]) / 2.0


def unidades_plausibles(areas_dibujo: Sequence[float]) -> List[str]:
    """Unidades de dibujo con las que la mediana de `areas_dibujo` daría
    estancias de un tamaño creíble.

    Se usa la mediana y no la media porque un único polígono enorme —el
    contorno de toda la planta, un contorno agrupador que aún no se ha
    descartado— arrastraría la media y no mueve la mediana.

    Devuelve como mucho un elemento por la garantía de separación documentada
    en `AREA_PLAUSIBLE_MAX_M2`, pero se devuelve lista porque quien llama no
    tiene por qué depender de esa propiedad.
    """
    positivas = [a for a in areas_dibujo if a > 0]
    if len(positivas) < MINIMO_ESTANCIAS_PARA_PLAUSIBILIDAD:
        return []

    mediana = _mediana(positivas)
    compatibles = []
    for nombre in ORDEN_HIPOTESIS:
        factor = factor_de_unidad(nombre)
        en_m2 = mediana * factor * factor
        if AREA_PLAUSIBLE_MIN_M2 <= en_m2 <= AREA_PLAUSIBLE_MAX_M2:
            compatibles.append(nombre)
    return compatibles


def detectar_escala(codigo_insunits: int, areas_dibujo: Sequence[float]) -> EscalaDetectada:
    """Cruza lo que declara la cabecera con lo que dice el tamaño de lo
    dibujado. Función pura: números dentro, decisión fuera.

    Los seis desenlaces posibles:

    - **acuerdo** — cabecera y tamaño coinciden. Se sigue sin preguntar.
    - **cabecera** — la cabecera declara una unidad métrica y no hay estancias
      suficientes para contrastarla. Se sigue: es la mejor información que hay.
    - **plausibilidad** — la cabecera no dice nada (`$INSUNITS = 0`, el caso más
      frecuente) pero el tamaño solo admite una lectura. Se sigue.
    - **conflicto** — cabecera y tamaño se contradicen. Se para. Este es el
      caso que salva el proyecto en milímetros con una plantilla que declara
      metros, y por eso el tamaño manda sobre la cabecera en la sugerencia:
      el dibujo es un hecho y la cabecera es una afirmación.
    - **indecidible** — ni cabecera ni tamaño deciden. Se para.
    - **no_metrico** — el archivo declara unidades imperiales. Se para y no se
      ofrece conversión.
    """
    mediana = _mediana([a for a in areas_dibujo if a > 0])
    hipotesis = unidades_plausibles(areas_dibujo)
    base = {
        "codigo_insunits": codigo_insunits,
        "hipotesis_por_tamano": hipotesis,
        "area_mediana_dibujo": mediana,
    }

    if codigo_insunits in NO_METRICOS:
        unidad = NO_METRICOS[codigo_insunits]
        return EscalaDetectada(
            factor=None, unidad="", origen="no_metrico", unidad_cabecera=unidad,
            mensaje=(
                "El archivo está dibujado en %s. ArchMuse solo evalúa proyectos en unidades "
                "métricas, porque todo su motor de reglas es el CTE español. Convierte el plano "
                "a metros y vuelve a subirlo." % unidad
            ),
            **base,
        )

    en_cabecera = UNIDADES_METRICAS.get(codigo_insunits)
    unidad_cabecera = en_cabecera[0] if en_cabecera else ""
    base["unidad_cabecera"] = unidad_cabecera

    # Un código métrico pero disparatado para un edificio (kilómetros,
    # nanómetros...) se trata igual que no tener cabecera: se ignora y se
    # decide por tamaño, porque lo que sea que pasara con esa plantilla no
    # tiene arreglo automático.
    if en_cabecera is None:
        if len(hipotesis) == 1:
            unidad = hipotesis[0]
            return EscalaDetectada(
                factor=factor_de_unidad(unidad), unidad=unidad, origen="plausibilidad",
                mensaje=(
                    "El archivo no declara sus unidades, pero por el tamaño de las estancias "
                    "(mediana de %s unidades²) está dibujado en %s." % (_fmt(mediana), unidad)
                ),
                **base,
            )
        return EscalaDetectada(
            factor=None, unidad="", origen="indecidible", sugerencia=None,
            mensaje=(
                "El archivo no declara sus unidades y no hay estancias suficientes para "
                "deducirlas por su tamaño. Indica en qué unidad está dibujado el plano."
            ),
            **base,
        )

    if not hipotesis:
        return EscalaDetectada(
            factor=en_cabecera[1], unidad=unidad_cabecera, origen="cabecera",
            mensaje=(
                "El archivo declara %s. No hay estancias suficientes para contrastarlo, "
                "así que se toma esa unidad." % unidad_cabecera
            ),
            **base,
        )

    if unidad_cabecera in hipotesis:
        return EscalaDetectada(
            factor=en_cabecera[1], unidad=unidad_cabecera, origen="acuerdo",
            mensaje=(
                "El archivo declara %s y el tamaño de las estancias lo confirma." % unidad_cabecera
            ),
            **base,
        )

    # La cabecera y el dibujo se contradicen. La sugerencia sigue al dibujo.
    sugerida = hipotesis[0]
    factor = factor_de_unidad(sugerida)
    return EscalaDetectada(
        factor=None, unidad="", origen="conflicto", sugerencia=sugerida,
        mensaje=(
            "El archivo declara %s, pero con esa unidad la estancia mediana saldría de %s m², "
            "lo cual es imposible. Por su tamaño, el plano parece estar en %s. Confirma cuál "
            "es la correcta." % (
                unidad_cabecera,
                _fmt(mediana * en_cabecera[1] * en_cabecera[1]),
                sugerida,
            )
        ),
        **base,
    )


def _fmt(valor: float) -> str:
    """Número legible para un mensaje dirigido al arquitecto: sin notación
    científica y sin arrastrar quince decimales."""
    if valor == 0:
        return "0"
    if valor >= 1000:
        return "{:,.0f}".format(valor).replace(",", ".")
    if valor >= 1:
        return "{:.1f}".format(valor).replace(".", ",")
    return "{:.6f}".format(valor).rstrip("0").rstrip(".").replace(".", ",")
