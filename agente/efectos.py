# -*- coding: utf-8 -*-
"""Efectos: qué cambia una Skill fuera de sí misma, y quién lo autoriza.

**El problema, en una frase de Pablo:** «pedir aprobación antes de efectos
importantes». La parte difícil no es preguntar, es saber **cuándo** hay que
preguntar sin dejarlo al criterio de quien escribe cada Skill — porque el
criterio de quien la escribe, con prisa, es siempre «esto no hace falta
preguntarlo».

**La solución es declarativa.** Un efecto no se detecta: se declara en el
manifiesto de la Skill, y el ejecutor se niega a ejecutar una Skill con un
efecto que nadie ha autorizado. Olvidarse de declararlo no es un atajo cómodo:
la Skill que escribe un fichero sin declarar `escribe_fichero` es una Skill que
falla su propia verificación, porque las verificaciones se ejecutan sobre lo
que la Skill dijo que iba a hacer.

**Por qué un catálogo cerrado y no cadenas libres.** Una interfaz tiene que
poder explicarle al arquitecto qué le está pidiendo autorizar, y no puede
hacerlo sobre un vocabulario que cada Skill inventa. Con seis efectos y su
frase en castellano, la pantalla de autorización se escribe una vez.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, Tuple

#: Escribe un fichero nuevo bajo el espacio del proyecto. Reversible: se borra.
ESCRIBE_FICHERO = "escribe_fichero"

#: Modifica un fichero que trajo el cliente. El efecto más serio del catálogo:
#: el original de un plano de trabajo no se toca ni con permiso, se copia.
MODIFICA_FICHERO_DEL_CLIENTE = "modifica_fichero_del_cliente"

#: Cuesta dinero. `ia/uso.py` lo mide y lo topa, pero medirlo no es autorizarlo.
GASTA_TOKENS = "gasta_tokens"

#: Sale a la red hacia un tercero (Catastro, BOE, IdP). Puede fallar, puede
#: tardar, y en algunos casos revela que este proyecto existe.
LLAMA_API_EXTERNA = "llama_api_externa"

#: Escribe en la memoria del proyecto. Casi siempre deseable, pero es un
#: efecto: cambia lo que ArchMuse creerá mañana.
ESCRIBE_MEMORIA = "escribe_memoria"

#: Entrega algo al exterior (correo, enlace compartido). Irreversible de hecho.
ENVIA_AL_EXTERIOR = "envia_al_exterior"

EFECTOS = (
    ESCRIBE_FICHERO,
    MODIFICA_FICHERO_DEL_CLIENTE,
    GASTA_TOKENS,
    LLAMA_API_EXTERNA,
    ESCRIBE_MEMORIA,
    ENVIA_AL_EXTERIOR,
)

#: Lo que se le enseña a la persona que autoriza. En su idioma, no en el nuestro.
DESCRIPCIONES: Dict[str, str] = {
    ESCRIBE_FICHERO: "Crear un fichero nuevo en el proyecto",
    MODIFICA_FICHERO_DEL_CLIENTE: "Modificar un fichero aportado por el cliente",
    GASTA_TOKENS: "Consumir crédito de modelo de lenguaje",
    LLAMA_API_EXTERNA: "Consultar un servicio externo (Catastro, BOE, mapas)",
    ESCRIBE_MEMORIA: "Guardar datos en la memoria del proyecto",
    ENVIA_AL_EXTERIOR: "Enviar información fuera de ArchMuse",
}

#: Efectos que NUNCA se autorizan de forma permanente, por sesión ni por
#: proyecto: exigen autorización para cada ejecución concreta. Son aquellos
#: cuyo daño no se deshace con un botón.
EXIGEN_AUTORIZACION_PUNTUAL: FrozenSet[str] = frozenset(
    {MODIFICA_FICHERO_DEL_CLIENTE, ENVIA_AL_EXTERIOR}
)


class EfectoDesconocido(ValueError):
    """Una Skill declara un efecto que no está en el catálogo."""


class EfectoNoAutorizado(PermissionError):
    """Se ha intentado ejecutar algo con un efecto que nadie ha autorizado.

    Es una excepción y no un valor de retorno a propósito: un efecto no
    autorizado tiene que interrumpir el paso, no colarse como «resultado
    parcial» y descubrirse cuando el fichero ya está escrito.
    """

    def __init__(self, quien: str, efectos: Iterable[str]) -> None:
        self.quien = quien
        self.efectos = tuple(efectos)
        detalle = "; ".join(DESCRIPCIONES.get(e, e) for e in self.efectos)
        super().__init__(
            "«%s» necesita autorización para: %s. No se ha ejecutado nada."
            % (quien, detalle)
        )


def validar(efectos: Iterable[str]) -> Tuple[str, ...]:
    """Normaliza y comprueba una declaración de efectos."""
    fuera = tuple(dict.fromkeys(efectos))
    desconocidos = [e for e in fuera if e not in EFECTOS]
    if desconocidos:
        raise EfectoDesconocido(
            "efecto(s) fuera del catálogo: %s; admitidos %s"
            % (desconocidos, list(EFECTOS))
        )
    return fuera


@dataclass(frozen=True)
class Autorizacion:
    """Lo que una persona ha permitido, y hasta dónde.

    `alcance` distingue tres cosas que se confunden fácilmente:

    - `"ejecucion"` — vale para **esta** ejecución y se acabó. Es lo único que
      admiten los efectos irreversibles.
    - `"proyecto"` — vale mientras se trabaje en este proyecto. Razonable para
      «consulta el Catastro» o «gasta tokens».
    - `"siempre"` — vale para cualquier proyecto de este usuario.

    Se guarda **quién** autorizó. Una autorización sin firma no sirve para nada
    el día que alguien pregunte quién dijo que se podía tocar ese plano.
    """

    efecto: str
    alcance: str
    autorizada_por: str
    nota: str = ""

    ALCANCES = ("ejecucion", "proyecto", "siempre")

    def __post_init__(self) -> None:
        if self.efecto not in EFECTOS:
            raise EfectoDesconocido("efecto «%s» fuera del catálogo" % self.efecto)
        if self.alcance not in self.ALCANCES:
            raise ValueError("alcance «%s» desconocido" % self.alcance)
        if not self.autorizada_por:
            raise ValueError("una autorización sin firma no es una autorización")
        if self.efecto in EXIGEN_AUTORIZACION_PUNTUAL and self.alcance != "ejecucion":
            raise ValueError(
                "«%s» solo admite alcance «ejecucion»: su daño no se deshace, así que "
                "no se autoriza en bloque" % self.efecto
            )


@dataclass(frozen=True)
class Autorizaciones:
    """El conjunto de lo permitido para una ejecución concreta."""

    concedidas: Tuple[Autorizacion, ...] = field(default_factory=tuple)

    def permite(self, efecto: str) -> bool:
        return any(a.efecto == efecto for a in self.concedidas)

    def faltan(self, efectos: Iterable[str]) -> Tuple[str, ...]:
        return tuple(e for e in efectos if not self.permite(e))

    def exigir(self, quien: str, efectos: Iterable[str]) -> None:
        """Portero. Lanza si falta alguna; no devuelve nada si todo está bien."""
        pendientes = self.faltan(efectos)
        if pendientes:
            raise EfectoNoAutorizado(quien, pendientes)

    def con(self, *nuevas: Autorizacion) -> "Autorizaciones":
        return Autorizaciones(concedidas=self.concedidas + tuple(nuevas))

    @staticmethod
    def de(efectos: Iterable[str], *, por: str, alcance: str = "ejecucion") -> "Autorizaciones":
        """Atajo para tests y para una interfaz que autoriza una lista de golpe."""
        return Autorizaciones(
            tuple(Autorizacion(efecto=e, alcance=alcance, autorizada_por=por) for e in efectos)
        )


#: Nada autorizado. Es el valor por defecto **a propósito**: una ejecución sin
#: autorizaciones explícitas no puede tocar nada de fuera.
NINGUNA = Autorizaciones()


def solicitud(quien: str, efectos: Iterable[str]) -> dict:
    """Lo que la interfaz enseña para pedir permiso. Estructurado, no prosa."""
    pendientes = list(dict.fromkeys(efectos))
    return {
        "quien": quien,
        "efectos": [
            {
                "efecto": e,
                "descripcion": DESCRIPCIONES.get(e, e),
                "reversible": e not in EXIGEN_AUTORIZACION_PUNTUAL,
                "alcance_maximo": (
                    "ejecucion" if e in EXIGEN_AUTORIZACION_PUNTUAL else "siempre"
                ),
            }
            for e in pendientes
        ],
    }
