"""Ámbito territorial: identidad, cadena y ámbitos sectoriales superpuestos.

Dos ideas gobiernan este módulo, ambas de `docs/design/NORMATIVE_RESOLUTION.md`:

1. **La identidad es el código INE, nunca el nombre** (§3.1). Los nombres
   cambian, se traducen y se repiten (hay varios "Villanueva de..."); los
   códigos no. El nombre es una etiqueta con alias.

2. **La profundidad de la cadena es variable, la determina el dato** (§3.1).
   Nada aquí asume cinco niveles: Portugal tendrá otros, y un área
   metropolitana no es un nivel sino un ámbito con miembros explícitos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

# Niveles con competencia normativa reconocida. `provincia` NO está: ninguna
# provincia española regula edificación (por eso tampoco hay directorio de
# provincia en el corpus). Está en el registro para desambiguar homónimos.
NIVELES_CON_CORPUS = ("estatal", "autonomico", "municipal")


@dataclass(frozen=True)
class Ambito:
    """Un nivel territorial concreto.

    `id` es la ruta jerárquica de códigos: `es`, `es.13`, `es.13.28.28115`.
    El prefijo hace visible el nivel en el propio identificador, que es lo que
    permite ver de un vistazo que dos reglas compiten por la misma materia en
    niveles distintos.
    """

    id: str
    nivel: str
    codigo: str
    nombre: str

    @property
    def tiene_corpus(self) -> bool:
        return self.nivel in NIVELES_CON_CORPUS


@dataclass(frozen=True)
class AmbitoSectorial:
    """Ámbito que se SUPERPONE, no que se hereda (§3.3).

    Patrimonio, inundabilidad, servidumbre aeroportuaria... no cuelgan del
    municipio: lo atraviesan. Se activan por un Fact del proyecto, no por la
    elección de municipio. Modelarlos como un sexto nivel de la ruta obligaría
    a que la cadena dependiera de la parcela y no del municipio, perdiendo
    toda la cacheabilidad.

    `declarado=None` significa que NO se ha declarado — que no es lo mismo que
    declarar que no aplica. Un sectorial sin declarar deja sus reglas en
    `aplica_no_evaluable` con la pregunta pendiente, nunca en `no_aplica`
    (`INFERENCE_ENGINE.md` §2.2: la ausencia de evidencia no es evidencia de
    ausencia).
    """

    id: str
    nombre: str
    declarado: Optional[bool] = None

    @property
    def desconocido(self) -> bool:
        return self.declarado is None


@dataclass(frozen=True)
class Procedencia:
    """De dónde salen los datos con los que se resolvió esta cadena.

    Viaja pegada al resultado siguiendo el principio de
    `docs/brain/KNOWLEDGE_GRAPH.md` §0.3: ningún valor se entrega desnudo,
    siempre como par (valor, origen). Aquí es lo que impide leer una cadena
    resuelta con la semilla manual como si viniera del fichero oficial del INE.
    """

    origen: str
    verificado: bool
    aviso: Optional[str] = None


@dataclass(frozen=True)
class CadenaAmbitos:
    """Cadena territorial resuelta, de lo general a lo concreto.

    `ambitos[0]` es siempre el país; el último, el ámbito más específico
    declarado. El resolver de normativa recorre esta lista para reunir las
    reglas candidatas.
    """

    ambitos: Tuple[Ambito, ...]
    sectoriales: Tuple[AmbitoSectorial, ...] = ()
    procedencia: Optional[Procedencia] = None

    def __post_init__(self):
        if not self.ambitos:
            raise ValueError("Una CadenaAmbitos no puede estar vacía")

    @property
    def pais(self) -> Ambito:
        return self.ambitos[0]

    @property
    def mas_especifico(self) -> Ambito:
        return self.ambitos[-1]

    def por_nivel(self, nivel: str) -> Optional[Ambito]:
        return next((a for a in self.ambitos if a.nivel == nivel), None)

    @property
    def ids_con_corpus(self) -> List[str]:
        """Ámbitos de los que hay que cargar reglas, de lo general a lo
        concreto. Es la lista exacta de directorios que el loader abre: de
        ahí que el coste de carga no dependa del tamaño total del corpus."""
        return [a.id for a in self.ambitos if a.tiene_corpus]

    @property
    def sectoriales_sin_declarar(self) -> List[AmbitoSectorial]:
        return [s for s in self.sectoriales if s.desconocido]

    def __str__(self) -> str:
        return " → ".join(f"{a.nombre} [{a.id}]" for a in self.ambitos)
