# -*- coding: utf-8 -*-
"""Verificación: que el agente compruebe su propio trabajo, y que la comprobación pueda fallar.

**El riesgo que este módulo tiene que evitar es el teatro.** Es facilísimo
escribir verificaciones que siempre pasan y sentirse cubierto: comprobar que el
resultado no es `None`, que la lista tiene elementos, que el fichero existe. Eso
no es verificar, es decorar. Una verificación vale exactamente lo que vale el
caso en el que **falla**.

De ahí las tres reglas del módulo:

1. Una verificación es **determinista** y no llama a un modelo. Pedirle a un LLM
   que revise lo que produjo otro LLM no es verificación, es una segunda opinión
   del mismo tipo — y cuesta dinero por añadir confianza que no ha ganado.
2. Una verificación que falla **no reintenta en bucle**. Marca el resultado como
   no verificado y sigue; el bucle de reintento es cómo se consume un
   presupuesto entero sin converger.
3. Una Skill **puede** no tener verificaciones, y entonces su salida se marca
   como no verificable. Lo que no puede es fingir que las tiene.
4. Una comprobación que **no ha podido ejecutarse** lo dice, y no se presenta
   como una que ha fallado (`NoSeHaPodidoComprobar`). No comprobar no es
   comprobar —sigue sin salir verificado—, pero acusar al plano del arquitecto
   de un defecto que no se ha llegado a mirar es peor que callarse.

**Las tres verificaciones genéricas de abajo son las que valen para cualquier
Skill** y por eso viven aquí: no inventar cifras, no dejar huecos mudos y no
declarar verificado lo que no se ha comprobado. Las específicas de dominio —que
la suma del cuadro de superficies cuadre, que el original conserve su sha256—
viven con su Skill, que es quien sabe qué significa estar bien.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence, Tuple


@dataclass(frozen=True)
class NoSeHaPodidoComprobar:
    """Lo que devuelve una verificacion que **no ha llegado a ejecutarse**.

    El tercer estado existe porque el primer plano real lo hizo falta. La
    comprobacion de que la suma del cuadro cuadra con la superficie medida no
    pudo correr —la geometria tenia recintos solapados y no habia superficie
    medida contra la que cruzar—, y el acta la presentaba como `[FALLA]`. Un
    arquitecto que lee «FALLA: la suma cuadra» entiende que su cuadro esta mal.
    Eso es una acusacion falsa sobre su trabajo, y es peor que no decir nada.

    «No se ha podido comprobar» tampoco es «pasa»: por eso NO cuenta como
    superada y una bloqueante en este estado sigue dejando el resultado sin
    verificar. Lo que cambia es **lo que se le dice al arquitecto**: que falta
    un dato, no que su plano falla.
    """

    motivo: str


@dataclass(frozen=True)
class ResultadoVerificacion:
    """Qué comprobó, si pasó y por qué no, si no pasó."""

    nombre: str
    ok: bool
    detalle: str = ""
    #: Se copia de la `Verificacion` que lo produjo. Vive aquí y no solo allí
    #: porque el acta se guarda y se vuelve a leer sin las funciones.
    bloqueante: bool = True
    #: La comprobación no llegó a ejecutarse por falta de un dato de entrada.
    #: Nunca va con `ok=True`: no comprobar no es comprobar. Va aparte de `ok`
    #: para que el acta pueda decir «no se ha podido comprobar» en vez de
    #: «falla», que es lo que el arquitecto lee como un defecto de su plano.
    no_procede: bool = False

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "ok": self.ok,
            "detalle": self.detalle,
            "bloqueante": self.bloqueante,
            "no_procede": self.no_procede,
        }


@dataclass(frozen=True)
class Verificacion:
    """Una comprobación declarada, con nombre estable y función determinista.

    `funcion` recibe lo que produjo la Skill y devuelve `True`, `False`, o una
    cadena con el motivo del fallo. Devolver la cadena es lo habitual: un
    `False` pelado obliga a quien lee el acta a adivinar qué pasó.
    """

    nombre: str
    descripcion: str
    funcion: Callable[..., Any]
    #: Si esta verificación es imprescindible. Una `bloqueante` que falla impide
    #: que el resultado se entregue como bueno; una no bloqueante solo avisa.
    bloqueante: bool = True

    def ejecutar(self, resultado: Any) -> ResultadoVerificacion:
        """Ejecuta la comprobación. **Nunca levanta**: un fallo de la propia
        verificación es un fallo de verificación, no una caída del sistema."""
        try:
            salida = self.funcion(resultado)
        except Exception as exc:  # noqa: BLE001 - una comprobación no tumba el trabajo
            return ResultadoVerificacion(
                nombre=self.nombre,
                ok=False,
                detalle="la verificación falló al ejecutarse: %s: %s"
                % (type(exc).__name__, exc),
            )
        if isinstance(salida, NoSeHaPodidoComprobar):
            return ResultadoVerificacion(
                nombre=self.nombre, ok=False, no_procede=True, detalle=salida.motivo
            )
        if salida is True:
            return ResultadoVerificacion(nombre=self.nombre, ok=True)
        if salida is False or salida is None:
            return ResultadoVerificacion(
                nombre=self.nombre, ok=False, detalle=self.descripcion
            )
        return ResultadoVerificacion(nombre=self.nombre, ok=False, detalle=str(salida))


@dataclass(frozen=True)
class Dictamen:
    """El veredicto conjunto sobre un resultado."""

    resultados: Tuple[ResultadoVerificacion, ...] = field(default_factory=tuple)

    @property
    def verificado(self) -> bool:
        """Verdadero solo si **hubo** comprobaciones y todas las bloqueantes pasaron.

        Que un resultado sin comprobaciones no salga verificado no es una
        tecnicidad: es la diferencia entre «lo he comprobado» y «no había nada
        que comprobar», y presentarlas igual es cómo se pierde la confianza.
        """
        return bool(self.resultados) and all(r.ok for r in self._bloqueantes())

    @property
    def avisos(self) -> Tuple[str, ...]:
        """Lo que ha fallado de verdad. **No incluye lo que no se pudo comprobar.**

        Mezclarlos haría que el arquitecto leyera «falta un dato de entrada» con
        el mismo peso que «tu cuadro no cuadra», y la segunda es la unica que le
        obliga a mirar el plano. Lo no comprobado va en `no_comprobadas`, que el
        acta imprime en su propia seccion.
        """
        return tuple(r.detalle or r.nombre
                     for r in self.resultados if not r.ok and not r.no_procede)

    @property
    def no_comprobadas(self) -> Tuple[str, ...]:
        """Las comprobaciones que no llegaron a ejecutarse, con su motivo."""
        return tuple("%s: %s" % (r.nombre, r.detalle or "sin motivo declarado")
                     for r in self.resultados if r.no_procede)

    def _bloqueantes(self) -> Tuple[ResultadoVerificacion, ...]:
        return tuple(r for r in self.resultados if r.bloqueante)

    def a_dict(self) -> dict:
        return {
            "verificado": self.verificado,
            "comprobaciones": [r.a_dict() for r in self.resultados],
            "avisos": list(self.avisos),
            "no_comprobadas": list(self.no_comprobadas),
        }


def dictaminar(verificaciones: Sequence[Verificacion], resultado: Any) -> Dictamen:
    """Ejecuta todas las verificaciones sobre un resultado y compone el dictamen."""
    salidas = []
    for v in verificaciones:
        r = v.ejecutar(resultado)
        salidas.append(
            ResultadoVerificacion(
                nombre=r.nombre, ok=r.ok, detalle=r.detalle, bloqueante=v.bloqueante,
                no_procede=r.no_procede,
            )
        )
    return Dictamen(resultados=tuple(salidas))


# --- Las tres genéricas -----------------------------------------------------

def _afirmaciones_de(resultado: Any) -> Tuple[Any, ...]:
    return tuple(getattr(resultado, "afirmaciones", ()) or ())


def toda_cifra_tiene_fuente() -> Verificacion:
    """Ninguna afirmación con valor puede carecer de quién la produjo.

    Es la versión estructurada de lo que `respaldo.py` hace sobre la prosa: allí
    se rastrea una cifra hasta el resultado de una herramienta; aquí se exige que
    la afirmación diga qué capacidad o Skill la emitió. Las dos hacen falta
    porque protegen dos superficies distintas.
    """

    def _comprobar(resultado: Any):
        huerfanas = [
            a.nombre
            for a in _afirmaciones_de(resultado)
            if a.valor is not None and not a.fuente
        ]
        if huerfanas:
            return "afirmaciones con valor y sin fuente: %s" % huerfanas
        return True

    return Verificacion(
        nombre="toda_cifra_tiene_fuente",
        descripcion="Cada dato con valor declara qué capacidad o Skill lo produjo.",
        funcion=_comprobar,
    )


def ningun_hueco_mudo() -> Verificacion:
    """Lo que no se sabe se dice con motivo. Un `UNKNOWN` sin motivo es un hueco
    que el arquitecto leerá como «no aplica», que es lo contrario de lo que es."""

    def _comprobar(resultado: Any):
        from analyzer.hechos import UNKNOWN

        mudas = [
            a.nombre
            for a in _afirmaciones_de(resultado)
            if a.estado == UNKNOWN and a.motivo is None
        ]
        if mudas:
            return "valores desconocidos sin motivo: %s" % mudas
        return True

    return Verificacion(
        nombre="ningun_hueco_mudo",
        descripcion="Todo lo desconocido lleva su motivo.",
        funcion=_comprobar,
    )


def las_inferencias_declaran_su_hipotesis() -> Verificacion:
    """Redundante con el constructor de `Afirmacion`, y a propósito.

    `Afirmacion.__post_init__` ya lo impide, así que esta verificación **no
    puede fallar hoy**. Existe porque el día que alguien construya una
    afirmación por otra vía —deserializándola, por ejemplo— la garantía se
    mantiene en el sitio donde se entrega el trabajo, y no solo donde se
    construye el objeto.
    """

    def _comprobar(resultado: Any):
        from .afirmacion import INFERENCIA

        sueltas = [
            a.nombre
            for a in _afirmaciones_de(resultado)
            if a.naturaleza == INFERENCIA and not a.hipotesis
        ]
        if sueltas:
            return "inferencias sin hipótesis declarada: %s" % sueltas
        return True

    return Verificacion(
        nombre="las_inferencias_declaran_su_hipotesis",
        descripcion="Toda inferencia dice de qué hipótesis depende.",
        funcion=_comprobar,
    )


def GENERICAS() -> Tuple[Verificacion, ...]:
    """Las que toda Skill debería tener salvo que tenga un motivo para no tenerlas."""
    return (
        toda_cifra_tiene_fuente(),
        ningun_hueco_mudo(),
        las_inferencias_declaran_su_hipotesis(),
    )


def valor_dentro_de(nombre_afirmacion: str, minimo: Optional[float] = None,
                    maximo: Optional[float] = None) -> Verificacion:
    """Comprobación de rango, que es la forma más común de detectar un disparate.

    Un cálculo de superficie que devuelve 4.000.000 m² para una vivienda no
    salta en ningún test unitario y sí en un rango declarado.
    """

    def _comprobar(resultado: Any):
        for a in _afirmaciones_de(resultado):
            if a.nombre != nombre_afirmacion or a.valor is None:
                continue
            try:
                v = float(a.valor)
            except (TypeError, ValueError):
                return "«%s» no es un número: %r" % (nombre_afirmacion, a.valor)
            if minimo is not None and v < minimo:
                return "«%s» = %s, por debajo del mínimo %s" % (nombre_afirmacion, v, minimo)
            if maximo is not None and v > maximo:
                return "«%s» = %s, por encima del máximo %s" % (nombre_afirmacion, v, maximo)
        return True

    return Verificacion(
        nombre="rango_de_%s" % nombre_afirmacion,
        descripcion="«%s» está entre %s y %s." % (nombre_afirmacion, minimo, maximo),
        funcion=_comprobar,
    )


def produce_lo_declarado(claves: Iterable[str]) -> Verificacion:
    """La Skill produjo lo que su manifiesto dice que produce.

    Es la verificación que convierte `produce` en una promesa comprobable en vez
    de en documentación. Una clave que la Skill no pudo producir tiene que estar
    presente como `UNKNOWN` con motivo — no ausente.
    """
    esperadas = tuple(claves)

    def _comprobar(resultado: Any):
        producidas = {a.nombre for a in _afirmaciones_de(resultado)}
        faltan = [c for c in esperadas if c not in producidas]
        if faltan:
            return (
                "el manifiesto promete %s y no aparecen: %s. Lo que no se ha podido "
                "producir tiene que decirse como desconocido con motivo, no omitirse."
                % (list(esperadas), faltan)
            )
        return True

    return Verificacion(
        nombre="produce_lo_declarado",
        descripcion="Aparecen todas las claves que el manifiesto declara producir.",
        funcion=_comprobar,
    )
