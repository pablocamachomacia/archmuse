# -*- coding: utf-8 -*-
"""`Skill`: procedimiento profesional reutilizable, declarado y verificable.

**Qué distingue una Skill de un prompt largo**, que es la pregunta que decide
si esto merece existir. Un prompt largo no se puede versionar sin romper lo
anterior, no declara qué necesita, no dice qué produce, no se puede verificar y
no se puede componer. Una Skill hace las cinco cosas, y por eso es un objeto y
no texto.

**Qué distingue una Skill de una Capacidad (`capacidad.py`).** Una capacidad es
*saber hacer una cosa*: resolver un ámbito territorial, leer un DXF, calcular
una superficie. Una Skill es *saber cómo se hace un trabajo*: qué se mira, en
qué orden, con qué comprobaciones, qué se entrega y qué se declara como no
comprobado. La capacidad es del ingeniero; la Skill es del arquitecto. Confundir
las dos es lo que produce funciones de 400 líneas con criterio profesional
enterrado dentro.

**Las cinco garantías que el `dataclass` hace cumplir, y no la buena voluntad:**

1. `requiere` — una Skill no se ejecuta sin sus datos. Cuando faltan, **la
   salida es la pregunta**, no un resultado con huecos.
2. `capacidades` — una Skill solo puede invocar las capacidades que declaró. El
   `Contexto` se niega a darle ninguna otra, así que el manifiesto no puede
   quedarse desactualizado sin que se note.
3. `produce` — lo prometido se comprueba. Una clave que no se pudo producir
   tiene que aparecer como desconocida **con motivo**, no desaparecer.
4. `efectos` — nada que toque el mundo exterior se ejecuta sin autorización.
5. `verificaciones` — el resultado se comprueba, y si no hay comprobaciones se
   dice que no las hay en vez de fingirlas.

**Versionado.** `version` es semver desde el primer día por un motivo concreto
del PRD: un proyecto revisado hace seis meses tiene que poder reproducir su
informe con la Skill que lo produjo. El acta fija `skill_id@version`, y una
Skill nueva no reescribe la historia de un proyecto viejo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from . import efectos as _efectos
from . import verificacion as _verif
from .afirmacion import Afirmacion
from .memoria import DATO, MemoriaDeProyecto
from .registro import CapacidadDesconocida, Registro


class SkillInvalida(ValueError):
    """Declaración de Skill que el sistema no admite. Se detecta al cargar."""


class RequisitosInsatisfechos(Exception):
    """La Skill no puede ejecutarse porque le faltan datos del proyecto.

    **No es un error, es el mejor momento del producto.** Lleva la lista de
    preguntas concretas que lo desbloquean, y llega **sin haber gastado un token
    ni tocado un fichero**: el chequeo es una consulta a la memoria.
    """

    def __init__(self, skill_id: str, faltan: Tuple[str, ...], preguntas: Tuple[str, ...]):
        self.skill_id = skill_id
        self.faltan = tuple(faltan)
        self.preguntas = tuple(preguntas)
        super().__init__(
            "«%s» necesita %s. Preguntas: %s" % (skill_id, list(self.faltan), list(self.preguntas))
        )


class CapacidadNoDeclarada(PermissionError):
    """La Skill ha intentado usar una capacidad que su manifiesto no declara."""


@dataclass(frozen=True)
class Requisito:
    """Un dato del proyecto sin el cual la Skill no debe ejecutarse.

    `pregunta` no es opcional. Un requisito sin la pregunta que lo desbloquea
    obliga al sistema a inventarse una («falta `territorial.municipio`»), y
    ninguna pregunta generada así sirve para que un arquitecto conteste.
    """

    clave: str
    pregunta: str
    #: Por defecto un valor `ESTIMATED` **no** basta: una tipología estimada por
    #: el sistema no es una tipología declarada por el arquitecto.
    admite_estimado: bool = False

    def __post_init__(self) -> None:
        if not self.clave or not self.pregunta:
            raise SkillInvalida("un requisito necesita clave y pregunta")


@dataclass(frozen=True)
class Entregable:
    """Algo que se le entrega al arquitecto.

    `borrador` es `True` y no hay forma de ponerlo a `False`: es C3 del
    documento de alineación estratégica, y la frontera legal del producto.
    ArchMuse asesora; el proyecto lo firma quien lo redacta.
    """

    nombre: str
    tipo: str                      # "dxf" | "pdf" | "json" | "texto" | "ifc"
    ruta: Optional[str] = None
    sello: Optional[str] = None    # sha256 de lo entregado
    borrador: bool = True

    def __post_init__(self) -> None:
        if not self.borrador:
            raise SkillInvalida(
                "no existe entregable que no sea borrador para revisión de un "
                "colegiado. Es la frontera legal del producto, no una opción."
            )

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre, "tipo": self.tipo, "ruta": self.ruta,
            "sello": self.sello, "borrador": self.borrador,
        }


@dataclass(frozen=True)
class ResultadoDeSkill:
    """Lo que produce una Skill. Nunca prosa suelta."""

    afirmaciones: Tuple[Afirmacion, ...] = field(default_factory=tuple)
    entregables: Tuple[Entregable, ...] = field(default_factory=tuple)
    #: Lo que hace falta preguntar para poder ir más lejos. No es un fallo.
    preguntas: Tuple[str, ...] = field(default_factory=tuple)
    #: Ramas que no se pudieron ejecutar, **con motivo**. Es lo que impide que
    #: «no comprobado» se lea como «comprobado y correcto».
    no_hecho: Tuple[str, ...] = field(default_factory=tuple)
    notas: Tuple[str, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict:
        return {
            "afirmaciones": [a.a_dict() for a in self.afirmaciones],
            "entregables": [e.a_dict() for e in self.entregables],
            "preguntas": list(self.preguntas),
            "no_hecho": list(self.no_hecho),
            "notas": list(self.notas),
        }


@dataclass(frozen=True)
class SalidaDeSkill:
    """El resultado más el dictamen de sus propias comprobaciones."""

    skill_id: str
    version: str
    resultado: ResultadoDeSkill
    dictamen: _verif.Dictamen

    @property
    def verificado(self) -> bool:
        return self.dictamen.verificado

    def a_dict(self) -> dict:
        return {
            "skill": "%s@%s" % (self.skill_id, self.version),
            "resultado": self.resultado.a_dict(),
            "dictamen": self.dictamen.a_dict(),
        }


class _MemoriaSoloLectura:
    """La memoria del proyecto sin sus dos verbos de escritura.

    **Por qué hace falta.** `Skill.ejecutar` comprueba las autorizaciones de los
    efectos declarados antes de empezar, pero eso no impide que una Skill que
    *no* declaró `escribe_memoria` llame a `memoria.declarar()` por su cuenta —
    y ahí el manifiesto habría dejado de decir la verdad sin que nada fallara.
    Con esto, escribir sin haberlo declarado no es una infracción de estilo: es
    un `AttributeError` en la primera ejecución.
    """

    _PROHIBIDOS = ("recordar", "declarar")

    def __init__(self, memoria: MemoriaDeProyecto, skill_id: str) -> None:
        object.__setattr__(self, "_memoria", memoria)
        object.__setattr__(self, "_skill_id", skill_id)

    def __getattr__(self, nombre: str):
        if nombre in self._PROHIBIDOS:
            raise AttributeError(
                "«%s» no declara el efecto «%s» y no puede escribir en la memoria "
                "del proyecto. Declara el efecto en su manifiesto."
                % (self._skill_id, _efectos.ESCRIBE_MEMORIA)
            )
        return getattr(self._memoria, nombre)


class Contexto:
    """Todo lo que una Skill puede tocar, y nada más.

    Es deliberadamente estrecho. Una Skill no recibe el registro entero ni la
    memoria cruda: recibe un objeto que **le impide** invocar una capacidad que
    no declaró y que registra cada invocación para el acta. La alternativa —
    pasarle el registro y confiar— convierte el manifiesto en documentación.
    """

    def __init__(self, skill: "Skill", *, memoria: MemoriaDeProyecto,
                 registro: Registro, autorizaciones: Optional[_efectos.Autorizaciones] = None,
                 argumentos: Optional[Dict[str, Any]] = None) -> None:
        self.skill = skill
        # Solo se entrega una memoria escribible a quien declaró el efecto.
        self.memoria = (
            memoria if _efectos.ESCRIBE_MEMORIA in skill.efectos
            else _MemoriaSoloLectura(memoria, skill.id)
        )
        self._memoria_real = memoria
        self.argumentos = dict(argumentos or {})
        self.autorizaciones = autorizaciones if autorizaciones is not None else _efectos.NINGUNA
        self._registro = registro
        #: Traza de invocaciones, en orden. Alimenta el acta.
        self.invocaciones: list = []

    # -- Capacidades --------------------------------------------------------

    def invocar(self, capacidad_id: str, **argumentos) -> dict:
        """Ejecuta una capacidad **declarada** por esta Skill."""
        if capacidad_id not in self.skill.capacidades:
            raise CapacidadNoDeclarada(
                "«%s» no declara la capacidad «%s»; declaradas: %s. Añádela al "
                "manifiesto: es lo que permite saber qué hace una Skill sin leerla."
                % (self.skill.id, capacidad_id, list(self.skill.capacidades))
            )
        capacidad = self._registro.buscar(capacidad_id)
        # Las autorizaciones de la Skill viajan hasta la capacidad: el portero
        # de efectos está en las dos capas y las dos miran lo mismo, así que no
        # hay forma de que una Skill autorizada para X invoque una capacidad
        # que hace Y.
        resultado = capacidad.invocar(argumentos, self.autorizaciones)
        self.invocaciones.append(
            {
                "capacidad": capacidad.id,
                "version": capacidad.version,
                "argumentos": dict(argumentos),
                "ok": bool(resultado.get("ok")),
            }
        )
        return resultado

    def naturaleza_de(self, capacidad_id: str) -> str:
        return self._registro.buscar(capacidad_id).naturaleza

    def version_de(self, capacidad_id: str) -> str:
        return self._registro.buscar(capacidad_id).version

    # -- Memoria ------------------------------------------------------------

    def valor(self, clave: str, por_defecto=None):
        return self._memoria_real.valor(clave, por_defecto)

    def recordar(self, clave: str, afirmacion: Afirmacion, *, clase: str = DATO,
                 nota: str = ""):
        """Escribe en la memoria del proyecto. **Es un efecto** y se autoriza."""
        self.autorizaciones.exigir(self.skill.id, (_efectos.ESCRIBE_MEMORIA,))
        return self._memoria_real.recordar(
            clase, clave, afirmacion,
            registrado_por="%s@%s" % (self.skill.id, self.skill.version), nota=nota,
        )

    # -- Firma para las afirmaciones ----------------------------------------

    @property
    def firma(self) -> str:
        return "%s@%s" % (self.skill.id, self.skill.version)


@dataclass(frozen=True)
class Skill:
    """El procedimiento profesional, declarado."""

    id: str                                   # "revision.recorridos_de_evacuacion"
    version: str                              # semver
    dominio: str
    #: Qué resuelve, en una frase que el planificador lee para elegirla.
    objetivo: str
    #: Cuándo usarla y cuándo no. Lo segundo importa más: sin ello, el
    #: planificador la elige para todo lo que se le parezca de lejos.
    cuando_usarla: str
    #: El procedimiento, en castellano profesional. No es documentación: es lo
    #: que se le enseña al arquitecto para que juzgue si el método es el suyo.
    procedimiento: Tuple[str, ...]
    requiere: Tuple[Requisito, ...]
    capacidades: Tuple[str, ...]
    produce: Tuple[str, ...]
    funcion: Callable[[Contexto], ResultadoDeSkill]
    #: JSON Schema de los argumentos de invocación — lo que NO viene de la
    #: memoria del proyecto sino de esta petición concreta («estos requisitos,
    #: de este correo»). La mayoría de Skills no tienen ninguno: sus datos son
    #: del proyecto, no de la orden, y por eso el valor por defecto es un objeto
    #: vacío y cerrado en vez de uno que admita cualquier cosa.
    parametros: Dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {},
                                 "additionalProperties": False}
    )
    verificaciones: Tuple[_verif.Verificacion, ...] = field(default_factory=tuple)
    efectos: Tuple[str, ...] = field(default_factory=tuple)
    limitaciones: Tuple[str, ...] = field(default_factory=tuple)
    referencia_normativa: Optional[str] = None

    def __post_init__(self) -> None:
        if "." not in self.id:
            raise SkillInvalida(
                "«%s»: el id de una Skill lleva dominio («revision.evacuacion»). El "
                "espacio de nombres es lo que evita el registro plano de doscientas "
                "entradas sin orden." % self.id
            )
        if len(self.version.split(".")) != 3:
            raise SkillInvalida("«%s»: la versión «%s» no es semver" % (self.id, self.version))
        if not self.produce:
            raise SkillInvalida(
                "«%s» no declara qué produce. Una Skill que no promete nada no se "
                "puede verificar ni encadenar." % self.id
            )
        if not self.objetivo or not self.cuando_usarla:
            raise SkillInvalida(
                "«%s»: sin `objetivo` y `cuando_usarla` el planificador no puede "
                "elegirla por otra cosa que el parecido del nombre." % self.id
            )
        object.__setattr__(self, "efectos", _efectos.validar(self.efectos))

    @property
    def nombre_de_herramienta(self) -> str:
        """El `id` traducido a lo que la API admite, con prefijo `skill__`.

        El prefijo no es decorativo: es lo que permite que el bucle distinga una
        Skill de una capacidad sin consultar dos registros, y que el modelo vea
        en el propio nombre que está pidiendo un procedimiento completo y no una
        función suelta.
        """
        return "skill__%s" % self.id.replace(".", "__")

    def esquema(self) -> Dict[str, Any]:
        """El manifiesto convertido en herramienta para la API.

        Lleva `cuando_usarla` y las limitaciones **dentro de la descripción**
        porque es lo único que el modelo lee para elegir: un objetivo sin su
        «cuándo NO usarla» hace que la Skill se elija para todo lo que se le
        parezca de lejos.
        """
        partes = [self.objetivo.strip(), "CUÁNDO: " + self.cuando_usarla.strip()]
        if self.requiere:
            partes.append(
                "NECESITA del proyecto: " + ", ".join(r.clave for r in self.requiere)
            )
        if self.efectos:
            partes.append("EFECTOS que hay que autorizar: " + ", ".join(self.efectos))
        if self.limitaciones:
            partes.append("NO comprueba: " + "; ".join(self.limitaciones) + ".")
        return {
            "name": self.nombre_de_herramienta,
            "description": chr(10).join(partes),
            "input_schema": self.parametros,
        }

    # -- Comprobaciones previas, sin gastar nada ----------------------------

    def comprobar_registro(self, registro: Registro) -> None:
        """Que las capacidades declaradas existan **y que sus efectos estén
        declarados por la Skill**. Se llama al **descubrir**.

        Fallar aquí y no al ejecutar es la diferencia entre enterarse al
        arrancar y enterarse delante de un cliente.

        **La segunda comprobación es de la tarea `TL-2`.** Una Skill declara
        los efectos que se le autorizan; si invoca una capacidad que hace algo
        que la Skill no declaró —escribir un fichero, por ejemplo—, ese efecto
        ocurriría bajo una autorización concedida para otra cosa. La pantalla
        de autorización le habría enseñado al arquitecto una lista incompleta,
        que es peor que no enseñarle ninguna. Con esto, el manifiesto de una
        Skill **no puede mentir por omisión**: o declara el efecto, o no puede
        declarar la capacidad que lo tiene.
        """
        for capacidad_id in self.capacidades:
            try:
                capacidad = registro.buscar(capacidad_id)
            except CapacidadDesconocida as exc:
                raise SkillInvalida(
                    "«%s» declara la capacidad «%s», que no existe: %s"
                    % (self.id, capacidad_id, exc)
                ) from exc
            sin_declarar = [e for e in capacidad.efectos if e not in self.efectos]
            if sin_declarar:
                raise SkillInvalida(
                    "«%s» declara la capacidad «%s», que tiene el/los efecto(s) %s, y la "
                    "Skill no los declara. Ocurrirían bajo una autorización concedida "
                    "para otra cosa: declara el efecto en la Skill o no uses esa capacidad."
                    % (self.id, capacidad_id, sin_declarar)
                )

    def faltantes(self, memoria: MemoriaDeProyecto) -> Tuple[Requisito, ...]:
        return tuple(
            r for r in self.requiere
            if not memoria.satisface(r.clave, admite_estimado=r.admite_estimado)
        )

    def puede_ejecutarse(self, memoria: MemoriaDeProyecto,
                         autorizaciones: _efectos.Autorizaciones) -> Tuple[bool, str]:
        """(puede, motivo). Determinista, gratis, y sin efectos secundarios."""
        faltan = self.faltantes(memoria)
        if faltan:
            return False, "faltan datos: %s" % [r.clave for r in faltan]
        sin_permiso = autorizaciones.faltan(self.efectos)
        if sin_permiso:
            return False, "faltan autorizaciones: %s" % list(sin_permiso)
        return True, "todo lo que necesita está disponible"

    # -- Ejecución ----------------------------------------------------------

    def todas_las_verificaciones(self) -> Tuple[_verif.Verificacion, ...]:
        """Las declaradas, más las genéricas, más la promesa de `produce`.

        Las genéricas se añaden siempre y no se pueden quitar: son las que
        impiden una cifra sin fuente, un hueco mudo y una inferencia sin
        hipótesis. Una Skill puede añadir criterio; no puede renunciar al suelo.
        """
        return tuple(self.verificaciones) + _verif.GENERICAS() + (
            _verif.produce_lo_declarado(self.produce),
        )

    def ejecutar(self, contexto: Contexto) -> SalidaDeSkill:
        """El orden importa y es este: requisitos, permisos, trabajo, comprobación."""
        faltan = self.faltantes(contexto._memoria_real)
        if faltan:
            raise RequisitosInsatisfechos(
                self.id,
                tuple(r.clave for r in faltan),
                tuple(r.pregunta for r in faltan),
            )
        contexto.autorizaciones.exigir(self.id, self.efectos)

        resultado = self.funcion(contexto)
        if not isinstance(resultado, ResultadoDeSkill):
            raise SkillInvalida(
                "«%s» devolvió %s en vez de un ResultadoDeSkill"
                % (self.id, type(resultado).__name__)
            )
        dictamen = _verif.dictaminar(self.todas_las_verificaciones(), resultado)
        return SalidaDeSkill(
            skill_id=self.id, version=self.version, resultado=resultado, dictamen=dictamen
        )

    # -- Manifiesto ---------------------------------------------------------

    def manifiesto(self) -> dict:
        """Lo que se le enseña al planificador y a una interfaz. Sin funciones."""
        return {
            "id": self.id,
            "version": self.version,
            "dominio": self.dominio,
            "objetivo": self.objetivo,
            "cuando_usarla": self.cuando_usarla,
            "procedimiento": list(self.procedimiento),
            "requiere": [
                {"clave": r.clave, "pregunta": r.pregunta, "admite_estimado": r.admite_estimado}
                for r in self.requiere
            ],
            "capacidades": list(self.capacidades),
            "produce": list(self.produce),
            "parametros": self.parametros,
            "efectos": list(self.efectos),
            "verificaciones": [v.nombre for v in self.todas_las_verificaciones()],
            "limitaciones": list(self.limitaciones),
            "referencia_normativa": self.referencia_normativa,
        }
