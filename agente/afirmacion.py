# -*- coding: utf-8 -*-
"""`Afirmacion`: distinguir un hecho de un cálculo, de una inferencia y de una propuesta.

**Por qué esto es lo primero que se construye.** Pablo lo puso en la lista de
lo que el agente debe saber hacer, y no es un detalle de presentación: es la
frontera entre asesorar y firmar. Un arquitecto que recibe cuatro frases
seguidas —«la parcela tiene 412 m²», «la ocupación resultante es del 38 %»,
«probablemente sea suelo urbano consolidado», «yo movería el núcleo de
comunicación al testero»— necesita saber cuál de las cuatro puede llevar a
proyecto sin comprobar. Si el sistema las presenta todas con el mismo tono, el
arquitecto tiene que verificarlas todas, y entonces el sistema no le ha ahorrado
nada.

**El vocabulario no se inventa: se compone.** El repositorio ya tiene dos ejes
ortogonales en `analyzer/hechos.py` y `modelo/atributo.py` —estado (`KNOWN`,
`ESTIMATED`, `UNKNOWN`, `NO_APLICABLE`) por origen (`observado`, `declarado`,
`derivado`, `supuesto`)— y hay una decisión escrita de Pablo del 2026-08-11 de
no añadir un tercer vocabulario. Aquí no se añade: **la naturaleza es una
proyección del origen**, con una sola incorporación real, `propuesta`, que el
modelo de hechos no podía expresar porque no es un dato del proyecto sino algo
que el sistema sugiere hacerle.

    HECHO       ← origen `observado` o `declarado`. Se leyó del fichero o lo
                  dijo el arquitecto. No lo ha producido ArchMuse.
    CALCULO     ← origen `derivado` por una capacidad DETERMINISTA. Reproducible
                  y verificable: misma entrada, mismo número, siempre.
    INFERENCIA  ← origen `supuesto`, o `derivado` por una capacidad `llm`. Hay
                  un salto que no es aritmética. Viaja con su hipótesis.
    PROPUESTA   ← no es un dato del proyecto: es una recomendación. Nunca puede
                  presentarse como cualquiera de las tres anteriores.

**La regla que hace esto útil y no decorativo:** una capacidad de naturaleza
`llm` NO puede emitir un `HECHO` ni un `CALCULO`. Está en el ADR, y aquí se hace
cumplir por construcción en vez de por revisión de código.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from analyzer.hechos import ESTADOS, KNOWN, UNKNOWN, Motivo
from modelo.atributo import DECLARADO, DERIVADO, OBSERVADO, ORIGENES, SUPUESTO

HECHO = "hecho"
CALCULO = "calculo"
INFERENCIA = "inferencia"
PROPUESTA = "propuesta"

NATURALEZAS = (HECHO, CALCULO, INFERENCIA, PROPUESTA)

#: Cómo se lee cada naturaleza en la interfaz. No es cosmética: es lo que el
#: arquitecto usa para decidir qué verifica y qué no.
ETIQUETAS = {
    HECHO: "Dato del proyecto",
    CALCULO: "Calculado por ArchMuse",
    INFERENCIA: "Deducido, con hipótesis",
    PROPUESTA: "Propuesta, decide el arquitecto",
}

#: Origen epistémico admisible para cada naturaleza. La `propuesta` no tiene
#: origen en el vocabulario de `modelo/atributo.py` porque no es un dato del
#: proyecto: es algo que ArchMuse sugiere, y por eso va aparte.
_ORIGENES_DE = {
    HECHO: (OBSERVADO, DECLARADO),
    CALCULO: (DERIVADO,),
    INFERENCIA: (DERIVADO, SUPUESTO),
    PROPUESTA: (),
}


class AfirmacionInvalida(ValueError):
    """Se ha intentado construir una afirmación que el vocabulario no admite."""


@dataclass(frozen=True)
class Afirmacion:
    """Algo que ArchMuse sostiene, con qué clase de sostén.

    Los invariantes se hacen cumplir en `__post_init__`, calcados del patrón de
    `Hecho.__post_init__` y `Atributo`, porque un contrato que solo está en la
    documentación es un contrato que se incumple el primer martes con prisa.
    """

    nombre: str
    naturaleza: str
    valor: Any = None
    unidad: Optional[str] = None
    estado: str = KNOWN
    origen: Optional[str] = None
    #: Quién lo produjo: `capacidad_id@version` o `skill_id@version`. Es lo que
    #: convierte el acta en algo que se puede seguir hasta el código.
    fuente: str = ""
    #: Para `INFERENCIA`: la hipótesis sin la cual la afirmación no se sostiene.
    hipotesis: Tuple[str, ...] = ()
    motivo: Optional[Motivo] = None
    #: Referencia oficial, tal cual la devolvió la capacidad. Nunca redactada.
    cita: Optional[str] = None

    def __post_init__(self) -> None:
        if self.naturaleza not in NATURALEZAS:
            raise AfirmacionInvalida(
                "naturaleza «%s» desconocida; admitidas %s"
                % (self.naturaleza, list(NATURALEZAS))
            )
        if self.estado not in ESTADOS:
            raise AfirmacionInvalida("estado «%s» desconocido" % self.estado)

        admisibles = _ORIGENES_DE[self.naturaleza]
        if self.naturaleza == PROPUESTA:
            if self.origen is not None:
                raise AfirmacionInvalida(
                    "una propuesta no tiene origen epistémico: no es un dato del "
                    "proyecto, es una recomendación"
                )
        else:
            if self.origen not in ORIGENES:
                raise AfirmacionInvalida(
                    "origen «%s» desconocido; admitidos %s" % (self.origen, list(ORIGENES))
                )
            if self.origen not in admisibles:
                raise AfirmacionInvalida(
                    "un «%s» no puede tener origen «%s»; admitidos %s"
                    % (self.naturaleza, self.origen, list(admisibles))
                )

        if self.naturaleza == INFERENCIA and not self.hipotesis:
            raise AfirmacionInvalida(
                "una inferencia sin hipótesis declarada es un hecho disfrazado: "
                "di de qué depende «%s»" % self.nombre
            )
        if self.estado == UNKNOWN:
            if self.valor is not None:
                raise AfirmacionInvalida("un UNKNOWN no lleva valor: «%s»" % self.nombre)
            if self.motivo is None:
                raise AfirmacionInvalida(
                    "un UNKNOWN necesita motivo; sin él es un hueco mudo: «%s»" % self.nombre
                )

    # --- Lectura -----------------------------------------------------------

    @property
    def verificable(self) -> bool:
        """Si otro puede repetir esto y obtener lo mismo.

        Solo el cálculo determinista lo es. Un hecho depende del fichero de
        origen y una inferencia, de una hipótesis: los dos se pueden **revisar**,
        que no es lo mismo que reproducir.
        """
        return self.naturaleza == CALCULO

    @property
    def etiqueta(self) -> str:
        return ETIQUETAS[self.naturaleza]

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "naturaleza": self.naturaleza,
            "etiqueta": self.etiqueta,
            "valor": self.valor,
            "unidad": self.unidad,
            "estado": self.estado,
            "origen": self.origen,
            "fuente": self.fuente,
            "hipotesis": list(self.hipotesis),
            "motivo": (
                {"codigo": self.motivo.codigo, "detalle": self.motivo.detalle}
                if self.motivo
                else None
            ),
            "cita": self.cita,
            "verificable": self.verificable,
        }


# --- Constructores, que es como se usará el 90 % de las veces ---------------

def hecho(nombre: str, valor: Any, *, origen: str = OBSERVADO, fuente: str = "",
          unidad: Optional[str] = None, cita: Optional[str] = None) -> Afirmacion:
    return Afirmacion(nombre=nombre, naturaleza=HECHO, valor=valor, unidad=unidad,
                      origen=origen, fuente=fuente, cita=cita)


def calculo(nombre: str, valor: Any, *, fuente: str, unidad: Optional[str] = None,
            cita: Optional[str] = None) -> Afirmacion:
    return Afirmacion(nombre=nombre, naturaleza=CALCULO, valor=valor, unidad=unidad,
                      origen=DERIVADO, fuente=fuente, cita=cita)


def inferencia(nombre: str, valor: Any, *, hipotesis: Tuple[str, ...], fuente: str,
               unidad: Optional[str] = None, origen: str = SUPUESTO,
               cita: Optional[str] = None) -> Afirmacion:
    from analyzer.hechos import ESTIMATED

    return Afirmacion(nombre=nombre, naturaleza=INFERENCIA, valor=valor, unidad=unidad,
                      estado=ESTIMATED, origen=origen, fuente=fuente,
                      hipotesis=tuple(hipotesis), cita=cita)


def propuesta(nombre: str, texto: str, *, fuente: str) -> Afirmacion:
    return Afirmacion(nombre=nombre, naturaleza=PROPUESTA, valor=texto, fuente=fuente)


def desconocido(nombre: str, codigo: str, detalle: str, *, fuente: str = "") -> Afirmacion:
    """Lo que no se ha podido determinar, dicho con motivo. Nunca un hueco mudo."""
    return Afirmacion(nombre=nombre, naturaleza=HECHO, valor=None, estado=UNKNOWN,
                      origen=OBSERVADO, fuente=fuente,
                      motivo=Motivo(codigo=codigo, detalle=detalle))


def de_capacidad(nombre: str, valor: Any, *, capacidad_id: str, version: str,
                 naturaleza_capacidad: str, unidad: Optional[str] = None,
                 cita: Optional[str] = None,
                 hipotesis: Tuple[str, ...] = ()) -> Afirmacion:
    """Construye la afirmación que **le está permitido** emitir a una capacidad.

    Aquí se hace cumplir la regla del ADR: una capacidad `llm` no puede emitir
    un hecho ni un cálculo. No es una convención que alguien tenga que recordar
    en la revisión — es que no hay forma de construir el objeto.
    """
    fuente = "%s@%s" % (capacidad_id, version)
    if naturaleza_capacidad == "llm":
        if not hipotesis:
            hipotesis = ("producido por un modelo de lenguaje, no por un cálculo",)
        return inferencia(nombre, valor, hipotesis=hipotesis, fuente=fuente,
                          unidad=unidad, cita=cita)
    return calculo(nombre, valor, fuente=fuente, unidad=unidad, cita=cita)
