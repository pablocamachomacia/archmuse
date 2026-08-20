# -*- coding: utf-8 -*-
"""Plan y ejecutor: encadenar Skills, sobrevivir a un fallo y poder reanudar.

**Los tres comportamientos que este módulo tiene que garantizar** salen
directamente de lo que Pablo pidió, y los tres son de robustez, no de potencia:

1. **Continuar cuando una rama no se puede ejecutar.** De cinco comprobaciones
   de una revisión, una depende de una materia sin cobertura en el corpus. Las
   otras cuatro se ejecutan igual, y el informe dice que la quinta no se
   comprobó y por qué. Un ejecutor que aborta al primer fallo convierte un
   informe incompleto —útil— en ningún informe.
2. **Recuperarse de errores.** Un paso que revienta no tumba la ejecución: se
   registra con motivo, sus dependientes quedan sin hacer, el resto sigue.
3. **Reanudar.** Un trabajo interrumpido —el proceso se reinicia, el usuario
   cierra el portátil, el worker muere— se relanza y no repite lo ya hecho.
4. **Ejecutar a la vez lo que es independiente** (`AG-8`), sin que el resultado
   dependa de quién terminó antes. El planificador ya le pide al modelo que
   declare qué pasos no dependen entre sí; hasta ahora esa declaración se
   calculaba y se tiraba. La regla es conservadora y está en `Ejecutor`: nivel
   entero, lista blanca de efectos, y la bitácora siempre en el orden de
   `Plan.orden()`.

**Por qué esto y no Temporal.** Está razonado en
`docs/design/2026-08-18-revision-stack-2026.md` §2 con criterio de reapertura
escrito. El resumen: las capacidades deterministas son idempotentes por
contrato, y con idempotencia la reanudación se reduce a «¿qué pasos ya están
sellados en la bitácora?». Eso son doscientas líneas, no un sistema.

**El sustrato de la bitácora es intercambiable** (`Bitacora`). Hoy ficheros;
mañana una tabla de Postgres con `tenant_id`. La forma de cada registro ya es
la de esa fila.
"""
from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from . import efectos as _efectos
from .memoria import MemoriaDeProyecto
from .registro import Registro, RegistroDeSkills, SkillDesconocida
from .skill import (
    CapacidadNoDeclarada,
    Contexto,
    RequisitosInsatisfechos,
    SalidaDeSkill,
    SkillInvalida,
)

# --- Estados de un paso -----------------------------------------------------

HECHO = "hecho"
FALLIDO = "fallido"
PENDIENTE_DE_DATOS = "pendiente_de_datos"
PENDIENTE_DE_AUTORIZACION = "pendiente_de_autorizacion"
NO_EJECUTADO = "no_ejecutado"          # una dependencia suya no salió bien
INTENTADO = "intentado"                # marca previa; ver `Ejecutor._marcar_intento`

ESTADOS = (HECHO, FALLIDO, PENDIENTE_DE_DATOS, PENDIENTE_DE_AUTORIZACION,
           NO_EJECUTADO, INTENTADO)

#: Los estados que **no** hay que reintentar al reanudar. Solo uno: lo hecho.
#: Un paso pendiente de datos se reintenta porque puede que ya los haya.
TERMINALES = (HECHO,)

#: Cuántos pasos de un mismo nivel se ejecutan a la vez como mucho (`AG-8`).
#: Cuatro y no «los que haya»: lo que se paraleliza son esperas de red, y
#: veinte peticiones simultáneas a Catastro no son veinte veces más rápidas —
#: son una forma de que Catastro deje de contestar. `1` lo desactiva.
MAX_PARALELO = 4


class PlanInvalido(ValueError):
    """El plan no se puede ejecutar. Se detecta **antes** de ejecutar nada."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sello(datos) -> str:
    crudo = json.dumps(datos, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()


# --- Plan -------------------------------------------------------------------

@dataclass(frozen=True)
class Paso:
    """Una Skill con sus argumentos y sus dependencias dentro del plan."""

    id: str
    skill: str                                   # "dominio.nombre" o "dominio.nombre@1.2.0"
    argumentos: Dict[str, object] = field(default_factory=dict)
    depende_de: Tuple[str, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict:
        return {
            "id": self.id, "skill": self.skill,
            "argumentos": dict(self.argumentos), "depende_de": list(self.depende_de),
        }


@dataclass(frozen=True)
class Plan:
    """Un grafo acíclico de pasos. Inspeccionable **antes** de ejecutarse.

    Que el plan sea un objeto y no una secuencia de decisiones sobre la marcha
    es lo que permite enseñárselo al arquitecto antes de tocar nada: qué Skills,
    en qué orden, qué datos faltan y qué efectos habrá que autorizar.
    """

    objetivo: str
    proyecto_id: str
    pasos: Tuple[Paso, ...] = field(default_factory=tuple)

    def validar(self, skills: RegistroDeSkills) -> Tuple[str, ...]:
        """Todos los motivos por los que este plan no se puede ejecutar.

        Devuelve la lista completa y no el primero: quien corrige un plan
        prefiere ver los cuatro problemas de una vez.
        """
        motivos: List[str] = []
        vistos = set()
        for p in self.pasos:
            if p.id in vistos:
                motivos.append("paso duplicado: «%s»" % p.id)
            vistos.add(p.id)
        for p in self.pasos:
            try:
                skills.buscar(p.skill)
            except SkillDesconocida as exc:
                motivos.append(str(exc))
            for d in p.depende_de:
                if d not in vistos:
                    motivos.append("«%s» depende de «%s», que no está en el plan" % (p.id, d))
        try:
            self.orden()
        except PlanInvalido as exc:
            motivos.append(str(exc))
        return tuple(motivos)

    def niveles(self) -> Tuple[Tuple[Paso, ...], ...]:
        """Los pasos agrupados por nivel topológico. Levanta si hay ciclo.

        **Dos pasos del mismo nivel no dependen el uno del otro**, ni directa
        ni indirectamente: es exactamente la independencia que el planificador
        le pide al modelo declarar, y hasta `AG-8` se calculaba aquí para
        tirarla acto seguido. `orden()` la aplana; el ejecutor no.

        Determinista y no «cualquiera que funcione»: los ids se ordenan dentro
        de cada nivel, así que dos ejecuciones del mismo plan producen los
        mismos niveles en el mismo orden, o la reanudación y el acta dejan de
        ser comparables.
        """
        por_id = {p.id: p for p in self.pasos}
        pendientes = {p.id: set(d for d in p.depende_de if d in por_id) for p in self.pasos}
        salida: List[Tuple[Paso, ...]] = []
        while pendientes:
            listos = sorted(pid for pid, deps in pendientes.items() if not deps)
            if not listos:
                raise PlanInvalido(
                    "el plan tiene un ciclo entre %s" % sorted(pendientes)
                )
            salida.append(tuple(por_id[pid] for pid in listos))
            for pid in listos:
                del pendientes[pid]
            for deps in pendientes.values():
                deps.difference_update(listos)
        return tuple(salida)

    def orden(self) -> Tuple[Paso, ...]:
        """El orden topológico aplanado, que es el orden **en serie**.

        Sigue existiendo y sigue siendo el orden de referencia: es el que fija
        cómo se apuntan los resultados en la bitácora, ejecute o no el ejecutor
        varios pasos a la vez. Que el orden del registro no dependa de quién
        terminó antes es lo que permite comparar dos ejecuciones del mismo plan.
        """
        return tuple(paso for nivel in self.niveles() for paso in nivel)

    def a_dict(self) -> dict:
        return {
            "objetivo": self.objetivo,
            "proyecto_id": self.proyecto_id,
            "pasos": [p.a_dict() for p in self.pasos],
        }


# --- Resultado de un paso ---------------------------------------------------

@dataclass(frozen=True)
class ResultadoDePaso:
    paso_id: str
    skill: str                       # `id@version` efectivo, no lo que pedía el plan
    estado: str
    momento: str = ""
    motivo: str = ""
    salida: Optional[dict] = None    # `SalidaDeSkill.a_dict()`
    preguntas: Tuple[str, ...] = field(default_factory=tuple)
    efectos_pendientes: Tuple[str, ...] = field(default_factory=tuple)
    sello: str = ""
    #: Sello de LO QUE ENTRO en el paso: su Skill y sus argumentos. Es lo que
    #: permite saber, al reanudar, si el paso «ficha» de hoy es el mismo paso
    #: «ficha» de ayer o solo se llama igual. Sin esto, replanificar reutiliza
    #: el resultado del paso viejo porque coincide el nombre.
    sello_de_entrada: str = ""

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError("estado de paso «%s» desconocido" % self.estado)
        if not self.momento:
            object.__setattr__(self, "momento", _ahora())

    def a_dict(self) -> dict:
        return {
            "paso_id": self.paso_id, "skill": self.skill, "estado": self.estado,
            "momento": self.momento, "motivo": self.motivo, "salida": self.salida,
            "preguntas": list(self.preguntas),
            "efectos_pendientes": list(self.efectos_pendientes),
            "sello": self.sello,
            "sello_de_entrada": self.sello_de_entrada,
        }

    @staticmethod
    def de_dict(d: dict) -> "ResultadoDePaso":
        return ResultadoDePaso(
            paso_id=d["paso_id"], skill=d["skill"], estado=d["estado"],
            momento=d.get("momento", ""), motivo=d.get("motivo", ""),
            salida=d.get("salida"), preguntas=tuple(d.get("preguntas") or ()),
            efectos_pendientes=tuple(d.get("efectos_pendientes") or ()),
            sello=d.get("sello", ""),
            sello_de_entrada=d.get("sello_de_entrada", ""),
        )


# --- Bitácora ---------------------------------------------------------------

class Bitacora(Protocol):
    """Dónde se apuntan los checkpoints. Append-only, como todo lo que importa."""

    def registrar(self, ejecucion_id: str, resultado: ResultadoDePaso) -> None: ...

    def leer(self, ejecucion_id: str) -> List[ResultadoDePaso]: ...


class BitacoraEnMemoria:
    def __init__(self) -> None:
        self._por_ejecucion: Dict[str, List[ResultadoDePaso]] = {}
        self._cerrojo = threading.Lock()

    def registrar(self, ejecucion_id: str, resultado: ResultadoDePaso) -> None:
        with self._cerrojo:
            self._por_ejecucion.setdefault(ejecucion_id, []).append(resultado)

    def leer(self, ejecucion_id: str) -> List[ResultadoDePaso]:
        with self._cerrojo:
            return list(self._por_ejecucion.get(ejecucion_id, ()))


class BitacoraEnFicheros:
    """Un JSONL por ejecución, escrito **antes y después** de cada paso."""

    def __init__(self, raiz: Optional[Path] = None) -> None:
        if raiz is None:
            from analyzer import storage

            raiz = Path(storage.data_dir()) / "ejecuciones"
        self.raiz = Path(raiz)
        self._cerrojo = threading.Lock()

    def _ruta(self, ejecucion_id: str) -> Path:
        seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in ejecucion_id)
        return self.raiz / ("%s.jsonl" % (seguro or "sin_id"))

    def registrar(self, ejecucion_id: str, resultado: ResultadoDePaso) -> None:
        ruta = self._ruta(ejecucion_id)
        with self._cerrojo:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(resultado.a_dict(), ensure_ascii=False, sort_keys=True))
                f.write("\n")

    def leer(self, ejecucion_id: str) -> List[ResultadoDePaso]:
        ruta = self._ruta(ejecucion_id)
        if not ruta.exists():
            return []
        fuera: List[ResultadoDePaso] = []
        with self._cerrojo, open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    try:
                        fuera.append(ResultadoDePaso.de_dict(json.loads(linea)))
                    except (ValueError, KeyError, TypeError):
                        continue
        return fuera


def _sello_de_entrada(paso: Paso) -> str:
    """Lo que entra en un paso: su Skill y sus argumentos. Nunca su resultado.

    Es lo que permite distinguir el paso «ficha» de hoy del paso «ficha» de
    ayer. Se sella la entrada y no la salida porque la pregunta al reanudar no
    es «¿salió lo mismo?» —eso no se sabe sin ejecutarlo— sino «¿es la misma
    petición?».
    """
    return _sello({"skill": paso.skill, "argumentos": dict(paso.argumentos)})


def _es_el_mismo_paso(paso: Paso, anterior: "ResultadoDePaso") -> bool:
    """Si el resultado guardado es de **este** paso o sólo de uno que se llama igual.

    La reanudación buscaba por `paso_id` a secas. Con un plan interrumpido y
    relanzado tal cual daba igual, porque el plan era el mismo; en cuanto entra
    la replanificación (`AG-4`) deja de darlo: el segundo plan puede reutilizar
    el id «ficha» para otra Skill o para los mismos argumentos cambiados, y
    reutilizar el resultado viejo sería entregar trabajo que **no** responde a
    lo que se pidió, con su sello y su acta, sin que nada fallara.

    **Un apunte antiguo sin `sello_de_entrada` se acepta.** La alternativa
    —rechazarlo— haría que estrenar esta comprobación repitiera todo el trabajo
    de las ejecuciones ya en curso, incluidas las que escribieron un fichero.
    La Skill sí se compara, que es lo que se podía comparar antes.
    """
    if anterior.skill.split("@")[0] != paso.skill.split("@")[0]:
        return False
    if not anterior.sello_de_entrada:
        return True
    return anterior.sello_de_entrada == _sello_de_entrada(paso)


# --- Resultado de la ejecución ---------------------------------------------

@dataclass(frozen=True)
class ResultadoDeEjecucion:
    ejecucion_id: str
    plan: Plan
    pasos: Tuple[ResultadoDePaso, ...] = field(default_factory=tuple)
    reanudados: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def completa(self) -> bool:
        """Se hizo todo lo que el plan decía, y el plan decía algo.

        La segunda mitad no es un detalle: `all()` de nada es cierto, así que
        una ejecución sin un solo paso —un plan vacío, uno rechazado, uno que
        el arquitecto no confirmó— se declaraba completa. Esa bandera viaja al
        acta, y un acta que dice `completa: true` sobre un trabajo que nadie
        hizo es exactamente la clase de afirmación que este sistema existe para
        no emitir.
        """
        return bool(self.pasos) and all(p.estado == HECHO for p in self.pasos)

    @property
    def preguntas(self) -> Tuple[str, ...]:
        """Todo lo que hay que preguntar para poder terminar, sin repetir."""
        fuera: List[str] = []
        for p in self.pasos:
            fuera.extend(p.preguntas)
        return tuple(dict.fromkeys(fuera))

    @property
    def efectos_pendientes(self) -> Tuple[str, ...]:
        fuera: List[str] = []
        for p in self.pasos:
            fuera.extend(p.efectos_pendientes)
        return tuple(dict.fromkeys(fuera))

    @property
    def no_hecho(self) -> Tuple[str, ...]:
        """Qué se quedó sin hacer y por qué. Es lo que impide leer un informe
        parcial como si fuera completo."""
        return tuple(
            "%s (%s): %s" % (p.paso_id, p.skill, p.motivo)
            for p in self.pasos
            if p.estado != HECHO
        )

    def salidas(self) -> Tuple[dict, ...]:
        return tuple(p.salida for p in self.pasos if p.estado == HECHO and p.salida)

    def a_dict(self) -> dict:
        return {
            "ejecucion_id": self.ejecucion_id,
            "plan": self.plan.a_dict(),
            "completa": self.completa,
            "pasos": [p.a_dict() for p in self.pasos],
            "reanudados": list(self.reanudados),
            "preguntas": list(self.preguntas),
            "efectos_pendientes": list(self.efectos_pendientes),
            "no_hecho": list(self.no_hecho),
        }


# --- El ejecutor ------------------------------------------------------------

class Ejecutor:
    """Ejecuta un plan de Skills con checkpoints, aislamiento de fallos y reanudación.

    **Sobre ejecutar a la vez (`AG-8`).** El planificador le dice al modelo que
    los pasos independientes se declaren independientes «porque es lo que
    permite ejecutarlos a la vez». Hasta ahora eso era mentira: `orden()`
    calculaba los niveles topológicos y los aplanaba. Ya no.

    La regla es **por nivel entero y con lista blanca**: un nivel se ejecuta a
    la vez sólo si *todos* sus pasos ejecutables son seguros en paralelo —sin
    efectos, o sólo con los de `efectos.SEGUROS_EN_PARALELO`— y hay más de uno.
    En cuanto uno del nivel escribe un fichero, toca la memoria del proyecto o
    hace algo irreversible, **el nivel entero va en serie**.

    Es deliberadamente conservador y cuesta algo de velocidad en los niveles
    mixtos. A cambio compra dos cosas que valen más: nadie tiene que razonar
    sobre interleavings para saber si un plan es seguro, y **la bitácora se
    escribe siempre en el orden de `orden()`**, no en el orden en que terminó
    cada hilo. Dos ejecuciones del mismo plan siguen siendo comparables línea a
    línea, que es de lo que depende la reanudación.
    """

    def __init__(self, *, capacidades: Registro, skills: RegistroDeSkills,
                 bitacora: Optional[Bitacora] = None,
                 max_paralelo: int = MAX_PARALELO) -> None:
        self._capacidades = capacidades
        self._skills = skills
        self._bitacora: Bitacora = bitacora if bitacora is not None else BitacoraEnMemoria()
        #: `1` desactiva el paralelismo del todo y deja el ejecutor exactamente
        #: como estaba. Es la salida de emergencia, y también cómo se comprueba
        #: en un test que el resultado no depende de ejecutar a la vez.
        self._max_paralelo = max(1, int(max_paralelo))

    # -- API ----------------------------------------------------------------

    def ejecutar(self, plan: Plan, memoria: MemoriaDeProyecto, *,
                 ejecucion_id: str,
                 autorizaciones: Optional[_efectos.Autorizaciones] = None
                 ) -> ResultadoDeEjecucion:
        motivos = plan.validar(self._skills)
        if motivos:
            raise PlanInvalido(
                "el plan no se puede ejecutar (%d motivo(s)): %s" % (len(motivos), list(motivos))
            )
        autorizaciones = autorizaciones if autorizaciones is not None else _efectos.NINGUNA

        previos = {r.paso_id: r for r in self._bitacora.leer(ejecucion_id)}
        hechos_antes = {pid for pid, r in previos.items() if r.estado in TERMINALES}

        resultados: Dict[str, ResultadoDePaso] = {}
        for nivel in plan.niveles():
            # Primero se resuelve, sin ejecutar nada, qué pasos de este nivel
            # hay que hacer de verdad. Los otros dos casos —lo ya hecho y lo
            # que depende de algo que no salió— se deciden mirando lo anterior.
            por_hacer: List[Tuple[Paso, Optional[ResultadoDePaso]]] = []
            for paso in nivel:
                anterior = previos.get(paso.id)
                if (anterior is not None and anterior.estado in TERMINALES
                        and _es_el_mismo_paso(paso, anterior)):
                    # Reanudación: no se repite lo hecho. Ni se recalcula, ni se
                    # vuelve a cobrar, ni se vuelve a escribir un fichero.
                    resultados[paso.id] = anterior
                    continue

                sin_hacer = [
                    d for d in paso.depende_de
                    if resultados.get(d) is None or resultados[d].estado != HECHO
                ]
                if sin_hacer:
                    resultados[paso.id] = ResultadoDePaso(
                        paso_id=paso.id, skill=paso.skill, estado=NO_EJECUTADO,
                        motivo="depende de %s, que no se completó" % sin_hacer,
                        sello_de_entrada=_sello_de_entrada(paso),
                    )
                    self._bitacora.registrar(ejecucion_id, resultados[paso.id])
                    continue

                por_hacer.append((paso, anterior))

            if self._a_la_vez(por_hacer):
                self._ejecutar_nivel_a_la_vez(
                    por_hacer, memoria, autorizaciones, ejecucion_id, resultados)
                continue

            for paso, anterior in por_hacer:
                resultados[paso.id] = self._ejecutar_paso(
                    paso, memoria, autorizaciones, ejecucion_id, anterior
                )

        return ResultadoDeEjecucion(
            ejecucion_id=ejecucion_id,
            plan=plan,
            pasos=tuple(resultados[p.id] for p in plan.pasos),
            reanudados=tuple(sorted(hechos_antes)),
        )

    # -- Un nivel a la vez (AG-8) -------------------------------------------

    def _a_la_vez(self, por_hacer: Sequence[Tuple[Paso, Optional[ResultadoDePaso]]]) -> bool:
        """Si este nivel se puede ejecutar a la vez. Todo o nada.

        Basta con que **un** paso del nivel no sea seguro para que el nivel
        entero vaya en serie. Es más lento de lo estrictamente necesario y es a
        propósito: la alternativa —mezclar hilos y pasos con efectos dentro del
        mismo nivel— obliga a razonar sobre el orden en que se apuntan las
        marcas `INTENTADO`, y ese razonamiento se hace mal una vez y ya está.
        """
        if self._max_paralelo <= 1 or len(por_hacer) < 2:
            return False
        return all(self._es_seguro_en_paralelo(paso) for paso, _ in por_hacer)

    def _es_seguro_en_paralelo(self, paso: Paso) -> bool:
        """Un paso es seguro si **todos** sus efectos están en la lista blanca.

        Sin efectos declarados es el caso seguro por excelencia: la Skill no
        toca nada de fuera. Y si la Skill no se encuentra, la respuesta es que
        no: no saber qué hace algo no es lo mismo que saber que no hace nada.
        """
        try:
            skill = self._skills.buscar(paso.skill)
        except SkillDesconocida:
            return False
        return all(e in _efectos.SEGUROS_EN_PARALELO for e in skill.efectos)

    def _ejecutar_nivel_a_la_vez(
        self, por_hacer: Sequence[Tuple[Paso, Optional[ResultadoDePaso]]],
        memoria: MemoriaDeProyecto, autorizaciones: _efectos.Autorizaciones,
        ejecucion_id: str, resultados: Dict[str, ResultadoDePaso],
    ) -> None:
        """Ejecuta el nivel en hilos y apunta **después, en el orden del plan**.

        El orden del apunte es la mitad de esta función. Si cada hilo escribiera
        en la bitácora al terminar, el fichero saldría en el orden en que ganó
        la carrera, y dos ejecuciones del mismo plan dejarían de poder
        compararse línea a línea. Diferir el apunte es seguro justamente aquí y
        no en general: estos pasos no tienen efectos que deshacer, así que si el
        proceso muere a mitad del nivel, la reanudación los repite y no pasa
        nada — que es lo que ya hacía con un paso sin efectos que fallaba.

        Hilos y no procesos: lo que se solapa son esperas de red (Catastro, el
        BOE, el modelo), no cálculo. Un `ProcessPool` costaría serializar la
        memoria del proyecto y el registro entero para no ganar nada.
        """
        obreros = min(self._max_paralelo, len(por_hacer))
        with ThreadPoolExecutor(max_workers=obreros,
                                thread_name_prefix="archmuse-plan") as pozo:
            futuros = [
                pozo.submit(self._ejecutar_paso, paso, memoria, autorizaciones,
                            ejecucion_id, anterior, False)
                for paso, anterior in por_hacer
            ]
            for (paso, _), futuro in zip(por_hacer, futuros):
                resultados[paso.id] = futuro.result()

        for paso, _ in por_hacer:
            self._bitacora.registrar(ejecucion_id, resultados[paso.id])

    # -- Un paso ------------------------------------------------------------

    def _ejecutar_paso(self, paso: Paso, memoria: MemoriaDeProyecto,
                       autorizaciones: _efectos.Autorizaciones, ejecucion_id: str,
                       anterior: Optional[ResultadoDePaso],
                       registrar: bool = True) -> ResultadoDePaso:
        skill = self._skills.buscar(paso.skill)
        firma = "%s@%s" % (skill.id, skill.version)
        entrada = _sello_de_entrada(paso)

        # Un paso que se quedó a medias con un efecto irreversible NO se repite
        # sin volver a autorizarlo. La marca `INTENTADO` se escribió antes de
        # ejecutarlo, así que sobrevivió al corte aunque el resultado no.
        if anterior is not None and anterior.estado == INTENTADO:
            irreversibles = [
                e for e in skill.efectos if e in _efectos.EXIGEN_AUTORIZACION_PUNTUAL
            ]
            if irreversibles and not self._autorizado_de_nuevo(autorizaciones, irreversibles):
                return self._apuntar(registrar, ejecucion_id, ResultadoDePaso(
                    paso_id=paso.id, skill=firma, sello_de_entrada=entrada, estado=PENDIENTE_DE_AUTORIZACION,
                    motivo=("se interrumpió a mitad y su efecto no se deshace: hace "
                            "falta autorizarlo otra vez antes de repetirlo"),
                    efectos_pendientes=tuple(irreversibles),
                ))

        if any(e in _efectos.EXIGEN_AUTORIZACION_PUNTUAL for e in skill.efectos):
            self._marcar_intento(ejecucion_id, paso, firma)

        contexto = Contexto(
            skill, memoria=memoria, registro=self._capacidades,
            autorizaciones=autorizaciones, argumentos=paso.argumentos,
        )
        try:
            salida: SalidaDeSkill = skill.ejecutar(contexto)
        except RequisitosInsatisfechos as exc:
            return self._apuntar(registrar, ejecucion_id, ResultadoDePaso(
                paso_id=paso.id, skill=firma, sello_de_entrada=entrada, estado=PENDIENTE_DE_DATOS,
                motivo="faltan datos del proyecto: %s" % list(exc.faltan),
                preguntas=exc.preguntas,
            ))
        except _efectos.EfectoNoAutorizado as exc:
            return self._apuntar(registrar, ejecucion_id, ResultadoDePaso(
                paso_id=paso.id, skill=firma, sello_de_entrada=entrada, estado=PENDIENTE_DE_AUTORIZACION,
                motivo=str(exc), efectos_pendientes=exc.efectos,
            ))
        except (CapacidadNoDeclarada, SkillInvalida) as exc:
            # Defecto de la propia Skill: no es un fallo de datos ni de permisos.
            return self._apuntar(registrar, ejecucion_id, ResultadoDePaso(
                paso_id=paso.id, skill=firma, sello_de_entrada=entrada, estado=FALLIDO,
                motivo="la Skill está mal declarada: %s" % exc,
            ))
        except Exception as exc:  # noqa: BLE001 - un paso no puede tumbar el plan
            return self._apuntar(registrar, ejecucion_id, ResultadoDePaso(
                paso_id=paso.id, skill=firma, sello_de_entrada=entrada, estado=FALLIDO,
                motivo="%s: %s" % (type(exc).__name__, exc),
            ))

        cuerpo = salida.a_dict()
        cuerpo["invocaciones"] = list(contexto.invocaciones)
        return self._apuntar(registrar, ejecucion_id, ResultadoDePaso(
            paso_id=paso.id, skill=firma, sello_de_entrada=entrada, estado=HECHO, salida=cuerpo,
            preguntas=salida.resultado.preguntas,
            motivo="" if salida.verificado else "resultado NO verificado: %s"
                   % list(salida.dictamen.avisos),
            sello=_sello(cuerpo),
        ))

    # -- Auxiliares ---------------------------------------------------------

    def _apuntar(self, registrar: bool, ejecucion_id: str,
                 resultado: ResultadoDePaso) -> ResultadoDePaso:
        """Apunta el resultado, salvo cuando lo apunta el nivel por su cuenta.

        `registrar=False` lo usa únicamente `_ejecutar_nivel_a_la_vez`, que
        apunta el nivel entero al final y en el orden del plan. Es el único
        sitio donde diferir es seguro, y es el único que lo pasa.
        """
        if registrar:
            self._bitacora.registrar(ejecucion_id, resultado)
        return resultado

    def _marcar_intento(self, ejecucion_id: str, paso: Paso, firma: str) -> None:
        """Se escribe **antes** de ejecutar, y ese orden es todo el mecanismo.

        Si el proceso muere a mitad, en la bitácora queda la marca de que se
        intentó pero no el resultado — que es exactamente la señal de «esto pudo
        quedar a medias» que la reanudación necesita.
        """
        self._bitacora.registrar(ejecucion_id, ResultadoDePaso(
            paso_id=paso.id, skill=firma, estado=INTENTADO,
            sello_de_entrada=_sello_de_entrada(paso),
            motivo="a punto de ejecutar un efecto que no se deshace",
        ))

    @staticmethod
    def _autorizado_de_nuevo(autorizaciones: _efectos.Autorizaciones,
                             irreversibles: Sequence[str]) -> bool:
        return not autorizaciones.faltan(irreversibles)
