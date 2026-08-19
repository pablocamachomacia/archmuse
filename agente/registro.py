# -*- coding: utf-8 -*-
"""El registro de capacidades, poblado por descubrimiento y no por import manual.

**Por qué descubrimiento.** Un registro central que hay que editar para añadir
una capacidad es un `if/elif` con otro nombre: la primera versión tiene cinco
entradas, la de dentro de dos años tiene trescientas y nadie se atreve a
tocarla. `analyzer/evaluator.py::classify_problems` —382 líneas de `if/elif`—
es la demostración de que en este repositorio eso ya pasó una vez.

Aquí, dejar un fichero en `agente/herramientas/` que exponga `CAPACIDADES`
basta. Ningún `__init__.py` se toca. Es el mismo mecanismo con el que
`normativa/loader.py` descubre el corpus por la estructura del árbol, y por el
mismo motivo: añadir contenido no puede costar una release.

**Orden determinista.** Las capacidades se ordenan por `id`. No es estética:
los manifiestos viajan en el prefijo del prompt del planificador, y un orden
que cambie entre procesos invalida la caché de prompt en cada llamada y
encarece el planificador en silencio (riesgo anotado en V1-10).
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .capacidad import Capacidad

PAQUETE_POR_DEFECTO = "agente.herramientas"


class CapacidadDesconocida(KeyError):
    """El plan nombra una capacidad que el registro no tiene.

    Se rechaza con motivo y **sin ejecutar nada**. La alternativa —adivinar la
    más parecida— es la clase de conveniencia que convierte un error visible en
    un resultado plausible.
    """


class Registro:
    """Las capacidades disponibles, indexadas por sus dos nombres."""

    def __init__(self, capacidades: Tuple[Capacidad, ...]) -> None:
        self._por_id: Dict[str, Capacidad] = {}
        for c in sorted(capacidades, key=lambda c: c.id):
            if c.id in self._por_id:
                raise ValueError(f"capacidad duplicada en el registro: {c.id}")
            self._por_id[c.id] = c
        self._por_nombre = {c.nombre_de_herramienta: c for c in self._por_id.values()}

    def __iter__(self) -> Iterator[Capacidad]:
        return iter(self._por_id.values())

    def __len__(self) -> int:
        return len(self._por_id)

    def ids(self) -> Tuple[str, ...]:
        return tuple(self._por_id)

    def buscar(self, nombre: str) -> Capacidad:
        """Acepta el `id`, el nombre traducido para la API, o `id@version`.

        **La forma `id@version` existe para los planes guardados** (tarea
        `CAD-2`). Un plan de hace seis meses nombra la versión con la que se
        ejecutó; al reproducirlo hay que poder decir con certeza si lo que hay
        hoy en el registro es lo mismo. Las tres respuestas posibles son
        distintas y ninguna puede confundirse con otra:

        - **Es esa versión** — se ejecuta igual.
        - **Es una versión posterior compatible** (misma mayor) — se ejecuta,
          porque eso es exactamente lo que promete el semver del manifiesto.
        - **Es otra mayor** — NO se ejecuta. Se rechaza diciendo qué versión
          pidió el plan, cuál hay, y que el cambio es incompatible por
          definición. Ejecutar «lo más parecido» sería reescribir en silencio
          lo que se hizo aquel día, que es lo contrario de un registro
          defendible.
        """
        if "@" in nombre:
            identificador, _, pedida = nombre.partition("@")
            capacidad = self._por_id.get(identificador) or self._por_nombre.get(identificador)
            if capacidad is None:
                raise CapacidadDesconocida(
                    f"«{identificador}» no está en el registro; disponibles: {sorted(self._por_id)}"
                )
            if capacidad.version == pedida:
                return capacidad
            mayor_pedida = pedida.split(".")[0]
            mayor_actual = capacidad.version.split(".")[0]
            if mayor_pedida == mayor_actual:
                return capacidad
            raise CapacidadDesconocida(
                f"el plan pide {identificador}@{pedida} y en el registro hay "
                f"{capacidad.version}: son versiones mayores distintas, así que el "
                f"contrato cambió de forma incompatible. Reproducir este plan con la "
                f"versión de hoy daría un resultado que nadie calculó aquel día."
            )
        capacidad = self._por_id.get(nombre) or self._por_nombre.get(nombre)
        if capacidad is None:
            raise CapacidadDesconocida(
                f"«{nombre}» no está en el registro; disponibles: {sorted(self._por_id)}"
            )
        return capacidad

    def esquemas(self) -> List[dict]:
        """Los manifiestos como herramientas de la API, en orden estable."""
        return [c.esquema() for c in self]


def descubrir(paquete: str = PAQUETE_POR_DEFECTO) -> Tuple[Capacidad, ...]:
    """Importa cada módulo del paquete y recoge su tupla `CAPACIDADES`.

    Un módulo sin `CAPACIDADES` se ignora en silencio a propósito: permite
    tener ayudantes privados junto a las herramientas sin que el registro se
    queje ni obligue a inventar una convención de nombres.
    """
    # Sin esto, un fichero dejado en el paquete después de arrancar el proceso
    # no se ve: el buscador de importaciones cachea el listado del directorio.
    importlib.invalidate_caches()
    modulo_paquete = importlib.import_module(paquete)
    encontradas: List[Capacidad] = []
    for info in sorted(
        pkgutil.iter_modules(modulo_paquete.__path__), key=lambda i: i.name
    ):
        if info.name.startswith("_"):
            continue
        modulo = importlib.import_module(f"{paquete}.{info.name}")
        for c in getattr(modulo, "CAPACIDADES", ()):
            if not isinstance(c, Capacidad):
                raise TypeError(
                    f"{paquete}.{info.name}: CAPACIDADES contiene un "
                    f"{type(c).__name__}, no una Capacidad"
                )
            encontradas.append(c)
    return tuple(encontradas)


_CACHE: Optional[Registro] = None


def registro(paquete: str = PAQUETE_POR_DEFECTO, recargar: bool = False) -> Registro:
    """El registro del proceso. Se descubre una vez; `recargar` es para los tests."""
    global _CACHE
    if _CACHE is None or recargar or paquete != PAQUETE_POR_DEFECTO:
        nuevo = Registro(descubrir(paquete))
        if paquete == PAQUETE_POR_DEFECTO:
            _CACHE = nuevo
        return nuevo
    return _CACHE


# --- Registro de Skills -----------------------------------------------------
#
# Vive aquí y no en un módulo aparte porque el mecanismo es exactamente el
# mismo —descubrimiento por fichero, orden estable, identificador único— y
# duplicarlo garantizaría que los dos se separen con el tiempo. Lo único
# distinto es que una Skill se valida contra el registro de capacidades: una
# Skill que declara una capacidad inexistente se rechaza al **cargarse**, no al
# ejecutarse delante de un cliente.

PAQUETE_DE_SKILLS = "agente.skills"


class SkillDesconocida(KeyError):
    """El plan nombra una Skill que el registro no tiene. Rechazo, no aproximación."""


class RegistroDeSkills:
    """Las Skills disponibles, indexadas por `id` y por `id@version`.

    **Las dos claves importan.** Por `id` se elige la Skill que se va a usar
    ahora; por `id@version` se reproduce lo que se hizo hace seis meses. Sin la
    segunda, publicar una Skill nueva reescribiría la historia de todos los
    proyectos que usaron la anterior — que es justo lo que el PRD prohíbe.
    """

    def __init__(self, skills) -> None:
        self._por_clave: Dict[str, Any] = {}
        self._ultima: Dict[str, Any] = {}
        for s in sorted(skills, key=lambda s: (s.id, s.version)):
            clave = "%s@%s" % (s.id, s.version)
            if clave in self._por_clave:
                raise ValueError("Skill duplicada en el registro: %s" % clave)
            self._por_clave[clave] = s
            self._ultima[s.id] = s      # el orden garantiza que gane la mayor

    def __iter__(self):
        return iter(self._ultima[k] for k in sorted(self._ultima))

    def __len__(self) -> int:
        return len(self._ultima)

    def ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._ultima))

    def buscar(self, nombre: str):
        """Acepta `id` (da la última versión) o `id@version` (da esa exacta)."""
        if nombre in self._por_clave:
            return self._por_clave[nombre]
        if nombre in self._ultima:
            return self._ultima[nombre]
        raise SkillDesconocida(
            "«%s» no está en el registro de Skills; disponibles: %s"
            % (nombre, sorted(self._ultima))
        )

    def manifiestos(self) -> List[dict]:
        """En orden estable, que es lo que hace que la caché del prompt acierte."""
        return [s.manifiesto() for s in self]


def descubrir_skills(paquete: str = PAQUETE_DE_SKILLS) -> Tuple[Any, ...]:
    """Importa cada módulo del paquete y recoge su tupla `SKILLS`."""
    importlib.invalidate_caches()
    try:
        modulo_paquete = importlib.import_module(paquete)
    except ModuleNotFoundError:
        return ()
    encontradas: List[Any] = []
    for info in sorted(pkgutil.iter_modules(modulo_paquete.__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        modulo = importlib.import_module("%s.%s" % (paquete, info.name))
        encontradas.extend(getattr(modulo, "SKILLS", ()))
    return tuple(encontradas)


_CACHE_SKILLS: Optional[RegistroDeSkills] = None


def registro_de_skills(paquete: str = PAQUETE_DE_SKILLS,
                       recargar: bool = False) -> RegistroDeSkills:
    """El registro de Skills del proceso, ya validado contra las capacidades."""
    global _CACHE_SKILLS
    if _CACHE_SKILLS is None or recargar or paquete != PAQUETE_DE_SKILLS:
        nuevo = RegistroDeSkills(descubrir_skills(paquete))
        capacidades = registro(recargar=recargar)
        for skill in nuevo:
            skill.comprobar_registro(capacidades)
        if paquete == PAQUETE_DE_SKILLS:
            _CACHE_SKILLS = nuevo
        return nuevo
    return _CACHE_SKILLS
