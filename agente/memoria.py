# -*- coding: utf-8 -*-
"""Memoria de proyecto: lo que el arquitecto ha dicho, y lo que ArchMuse ha averiguado.

**Por qué esta y no otra.** La auditoría §8 distingue tres memorias. Esta es la
primera porque sin ella la mitad de los objetivos que Pablo escribió son
imposibles de atender: «mejora este proyecto **respetando estas
restricciones**» exige saber cuáles son, y «prepárame la memoria justificativa»
exige saber el uso, la tipología y el municipio sin volver a preguntarlos cada
vez. Un agente que pregunta lo mismo tres veces no es un colaborador.

**Append-only, y no es purismo.** Un requisito del cliente cambia —«al final
queremos cuatro dormitorios, no tres»— y las dos versiones importan: la
segunda para trabajar, la primera para poder explicar por qué el plano de hace
un mes decía otra cosa. Sobrescribir borra la única prueba de que el cambio lo
pidió el cliente. Cada entrada, por tanto, se añade; la vigente es la última, y
el historial completo sigue ahí. Es la misma decisión que `graph_versions` en
el plan de migración, aplicada a algo que llega antes.

**Qué NO es.** No es un almacén de vectores, y aquí menos que en ningún sitio:
un requisito se recupera por su clave y su proyecto, con exactitud, no por
parecido semántico. Recuperar «el cliente quiere cuatro dormitorios» con un
0.83 de similitud sería un fallo, no una funcionalidad.

**Sustrato intercambiable a propósito.** Hoy son ficheros JSONL bajo el
directorio de datos; mañana serán filas de Postgres con `tenant_id` y RLS. La
forma de cada entrada ya es la de esa tabla, y cambiar de sustrato es
implementar `Sustrato` — no rehacer el módulo. Está anotado como D-6 en
`docs/design/decisiones-pendientes.md`.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

from analyzer.hechos import ESTIMATED, KNOWN
from modelo.atributo import DECLARADO

from .afirmacion import Afirmacion, HECHO, PROPUESTA

# --- Clases de entrada ------------------------------------------------------
# Qué es cada cosa, en el vocabulario del arquitecto y no en el del programador.

REQUISITO = "requisito"        # lo que el cliente pide. Cambia, y su historia importa
RESTRICCION = "restriccion"    # lo que no se puede hacer. Normativa, parcela, presupuesto
DECISION = "decision"          # lo que se ha resuelto, y por qué
DATO = "dato"                  # lo observado o calculado sobre el proyecto

CLASES = (REQUISITO, RESTRICCION, DECISION, DATO)


class MemoriaInvalida(ValueError):
    """Entrada que la memoria no admite."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Entrada:
    """Una cosa recordada, con quién la dijo y cuándo.

    `clave` es el identificador estable de *qué* se recuerda
    (`programa.dormitorios`, `territorial.municipio`); es lo que un requisito de
    Skill nombra. `afirmacion` lleva el valor **y su naturaleza epistémica**, así
    que la memoria no puede guardar un número sin decir de qué clase es.
    """

    proyecto_id: str
    clase: str
    clave: str
    afirmacion: Afirmacion
    registrado_por: str
    registrado_en: str = ""
    nota: str = ""

    def __post_init__(self) -> None:
        if self.clase not in CLASES:
            raise MemoriaInvalida(
                "clase «%s» desconocida; admitidas %s" % (self.clase, list(CLASES))
            )
        if not self.clave:
            raise MemoriaInvalida("una entrada de memoria sin clave no se puede recuperar")
        if not self.registrado_por:
            raise MemoriaInvalida(
                "falta `registrado_por`: sin saber quién lo dijo, un requisito no se "
                "puede discutir con el cliente"
            )
        if self.clase == REQUISITO and self.afirmacion.naturaleza == PROPUESTA:
            raise MemoriaInvalida(
                "una propuesta de ArchMuse no se guarda como requisito del cliente: "
                "el cliente no la ha pedido"
            )
        if not self.registrado_en:
            object.__setattr__(self, "registrado_en", _ahora())

    def a_dict(self) -> dict:
        return {
            "proyecto_id": self.proyecto_id,
            "clase": self.clase,
            "clave": self.clave,
            "afirmacion": self.afirmacion.a_dict(),
            "registrado_por": self.registrado_por,
            "registrado_en": self.registrado_en,
            "nota": self.nota,
        }

    @staticmethod
    def de_dict(d: dict) -> "Entrada":
        a = dict(d["afirmacion"])
        motivo = a.pop("motivo", None)
        a.pop("etiqueta", None)
        a.pop("verificable", None)
        if motivo:
            from analyzer.hechos import Motivo

            a["motivo"] = Motivo(codigo=motivo["codigo"], detalle=motivo["detalle"])
        a["hipotesis"] = tuple(a.get("hipotesis") or ())
        return Entrada(
            proyecto_id=d["proyecto_id"],
            clase=d["clase"],
            clave=d["clave"],
            afirmacion=Afirmacion(**a),
            registrado_por=d["registrado_por"],
            registrado_en=d.get("registrado_en", ""),
            nota=d.get("nota", ""),
        )


# --- Sustrato ---------------------------------------------------------------

class Sustrato(Protocol):
    """Dónde viven las entradas. Se cambia sin tocar la lógica de memoria."""

    def anadir(self, entrada: Entrada) -> None: ...

    def leer(self, proyecto_id: str) -> List[Entrada]: ...


class SustratoEnMemoria:
    """Para tests y para un proceso efímero. No sobrevive al proceso, y lo dice."""

    def __init__(self) -> None:
        self._por_proyecto: Dict[str, List[Entrada]] = {}
        self._cerrojo = threading.Lock()

    def anadir(self, entrada: Entrada) -> None:
        with self._cerrojo:
            self._por_proyecto.setdefault(entrada.proyecto_id, []).append(entrada)

    def leer(self, proyecto_id: str) -> List[Entrada]:
        with self._cerrojo:
            return list(self._por_proyecto.get(proyecto_id, ()))


class SustratoEnFicheros:
    """Un JSONL por proyecto. Append-only de verdad: solo se abre en modo «a».

    JSONL y no JSON: añadir una línea no exige reescribir el fichero, y un
    fichero truncado por un corte de luz pierde la última entrada en vez de
    todas — que en un formato que se lee entero es la diferencia entre perder
    un requisito y perder el proyecto.
    """

    def __init__(self, raiz: Optional[Path] = None) -> None:
        if raiz is None:
            from analyzer import storage

            raiz = Path(storage.data_dir()) / "memoria"
        self.raiz = Path(raiz)
        self._cerrojo = threading.Lock()

    def _ruta(self, proyecto_id: str) -> Path:
        seguro = "".join(c if c.isalnum() or c in "-_" else "_" for c in proyecto_id)
        if not seguro:
            raise MemoriaInvalida("identificador de proyecto vacío")
        return self.raiz / ("%s.jsonl" % seguro)

    def anadir(self, entrada: Entrada) -> None:
        ruta = self._ruta(entrada.proyecto_id)
        with self._cerrojo:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(entrada.a_dict(), ensure_ascii=False, sort_keys=True))
                f.write("\n")

    def leer(self, proyecto_id: str) -> List[Entrada]:
        ruta = self._ruta(proyecto_id)
        if not ruta.exists():
            return []
        fuera: List[Entrada] = []
        with self._cerrojo:
            with open(ruta, encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    try:
                        fuera.append(Entrada.de_dict(json.loads(linea)))
                    except (ValueError, KeyError, TypeError):
                        # Una línea corrupta no puede hacer desaparecer el resto
                        # de la memoria del proyecto. Se salta y se sigue.
                        continue
        return fuera


# --- La memoria -------------------------------------------------------------

@dataclass(frozen=True)
class Conflicto:
    """Dos valores vigentes e incompatibles para la misma clave.

    No se resuelve: manda el más reciente para poder seguir trabajando, y el
    conflicto se declara para que alguien lo mire. Elegir en silencio entre dos
    cosas que el cliente ha dicho es exactamente cómo se pierde un cliente.
    """

    clave: str
    anterior: Entrada
    vigente: Entrada


class MemoriaDeProyecto:
    """Lo que se sabe de un proyecto, con su procedencia y su historia."""

    def __init__(self, proyecto_id: str, sustrato: Optional[Sustrato] = None) -> None:
        if not proyecto_id:
            raise MemoriaInvalida("la memoria necesita un proyecto")
        self.proyecto_id = proyecto_id
        self._sustrato: Sustrato = sustrato if sustrato is not None else SustratoEnFicheros()

    # -- Escritura ----------------------------------------------------------

    def recordar(self, clase: str, clave: str, afirmacion: Afirmacion, *,
                 registrado_por: str, nota: str = "") -> Entrada:
        entrada = Entrada(
            proyecto_id=self.proyecto_id,
            clase=clase,
            clave=clave,
            afirmacion=afirmacion,
            registrado_por=registrado_por,
            nota=nota,
        )
        self._sustrato.anadir(entrada)
        return entrada

    def declarar(self, clave: str, valor, *, registrado_por: str, clase: str = REQUISITO,
                 unidad: Optional[str] = None, nota: str = "") -> Entrada:
        """Atajo para lo más frecuente: algo que ha dicho una persona.

        Origen `declarado`, naturaleza `hecho`: no lo ha medido ArchMuse ni lo
        ha deducido; lo ha dicho alguien, y así queda escrito.
        """
        from .afirmacion import Afirmacion as _A

        afirmacion = _A(nombre=clave, naturaleza=HECHO, valor=valor, unidad=unidad,
                        estado=KNOWN, origen=DECLARADO, fuente=registrado_por)
        return self.recordar(clase, clave, afirmacion, registrado_por=registrado_por, nota=nota)

    # -- Lectura ------------------------------------------------------------

    def todo(self) -> Tuple[Entrada, ...]:
        return tuple(self._sustrato.leer(self.proyecto_id))

    def historial(self, clave: str) -> Tuple[Entrada, ...]:
        """Todas las versiones de una clave, en orden de registro."""
        return tuple(e for e in self.todo() if e.clave == clave)

    def vigente(self, clave: str) -> Optional[Entrada]:
        """La última entrada de esa clave. Append-only: la última es la que manda."""
        historial = self.historial(clave)
        return historial[-1] if historial else None

    def valor(self, clave: str, por_defecto=None):
        entrada = self.vigente(clave)
        return entrada.afirmacion.valor if entrada is not None else por_defecto

    def por_clase(self, clase: str) -> Tuple[Entrada, ...]:
        """Las entradas **vigentes** de una clase, una por clave."""
        ultimas: Dict[str, Entrada] = {}
        for e in self.todo():
            if e.clase == clase:
                ultimas[e.clave] = e
        return tuple(ultimas[k] for k in sorted(ultimas))

    def conflictos(self) -> Tuple[Conflicto, ...]:
        """Claves cuya última entrada contradice a la anterior con valor distinto."""
        fuera: List[Conflicto] = []
        por_clave: Dict[str, List[Entrada]] = {}
        for e in self.todo():
            por_clave.setdefault(e.clave, []).append(e)
        for clave in sorted(por_clave):
            historial = por_clave[clave]
            if len(historial) < 2:
                continue
            anterior, vigente = historial[-2], historial[-1]
            if anterior.afirmacion.valor != vigente.afirmacion.valor:
                fuera.append(Conflicto(clave=clave, anterior=anterior, vigente=vigente))
        return tuple(fuera)

    # -- La consulta que usa el planificador --------------------------------

    def satisface(self, requisito: str, *, admite_estimado: bool = False) -> bool:
        """Si la memoria tiene ese requisito con base suficiente.

        `ESTIMATED` **no** cuenta salvo que la Skill lo declare expresamente. Es
        la regla que impide el «dato plausible»: una tipología estimada por el
        sistema no es una tipología declarada por el arquitecto, y una memoria
        justificativa construida sobre la primera es un problema con formato de
        entregable.
        """
        entrada = self.vigente(requisito)
        if entrada is None:
            return False
        estado = entrada.afirmacion.estado
        return estado == KNOWN or (admite_estimado and estado == ESTIMATED)

    def faltantes(self, requisitos: Iterable[str], *,
                  admite_estimado: bool = False) -> Tuple[str, ...]:
        return tuple(
            r for r in requisitos if not self.satisface(r, admite_estimado=admite_estimado)
        )

    def resumen(self) -> dict:
        """Lo que se le pasa al planificador: qué sabe, no cuánto ocupa.

        **Nunca la memoria entera.** El planificador recibe claves y estados —lo
        que necesita para decidir si una Skill puede ejecutarse— y no los
        valores completos, que engordarían el prompt sin cambiar la decisión.
        """
        return {
            "proyecto_id": self.proyecto_id,
            "claves": {
                e.clave: {
                    "clase": e.clase,
                    "estado": e.afirmacion.estado,
                    "naturaleza": e.afirmacion.naturaleza,
                }
                for e in sorted(
                    {e.clave: e for e in self.todo()}.values(), key=lambda e: e.clave
                )
            },
            "conflictos": [c.clave for c in self.conflictos()],
        }
