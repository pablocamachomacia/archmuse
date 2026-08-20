"""Entidades del corpus: NormaFuente, ReglaNormativa y sus satélites.

La decisión estructural viene de `docs/design/NORMATIVE_ENGINE.md` §2: **dos
entidades, no una.**

- **NormaFuente** es un hecho externo. La escribe un legislador, se publica en
  un boletín, entra en vigor y se deroga. No la controlamos. Nunca se evalúa:
  se cita.
- **ReglaNormativa** es nuestra interpretación. La escribe un curador, se
  revisa, se corrige. La controlamos por completo, y puede cambiar sin que la
  norma haya cambiado.

Meterlas en un solo registro con un solo contador de versión hace imposible
responder a la pregunta que formula cualquier reclamación de responsabilidad
profesional: **¿cambió la ley, o cambiamos nosotros de opinión?**

Bitemporalidad (§4): se almacenan dos ejes —vigencia legal y vigencia de
registro— y la aplicabilidad a un proyecto se CALCULA desde su fecha de
devengo. Nada se edita ni se borra: se cierra `registro_hasta` y se inserta
una fila nueva.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

# --- Catálogos cerrados -----------------------------------------------------

# 7 tipos de regla; 4 de ellos NO son evaluables, y eso es correcto: un corpus
# honesto contiene mucha norma que un motor geométrico no puede comprobar
# (`NORMATIVE_ENGINE.md` §6).
TIPOS_REGLA = {
    "exigencia_cuantitativa": True,
    "exigencia_de_presencia": True,
    "exigencia_compuesta": True,
    "exigencia_cualitativa": False,   # requiere juicio humano
    "definicion": False,              # define un término que otras usan
    "remision": False,                # no dice nada propio; remite
    "procedimental": False,           # trámite, régimen transitorio
}

# Los 5 patrones de CONSTRAINT_MODEL.md §3.1. CATÁLOGO CERRADO: añadir un
# sexto es un acto de gobernanza del Curador, jamás la reacción a una norma
# concreta que no encaja (CONSTRAINT_MODEL.md §14 lo nombra como el riesgo
# principal, y este corpus es exactamente donde esa presión aparece).
PATRONES = (
    "UMBRAL_SIMPLE",
    "UMBRAL_CON_EXCEPCION",
    "PRESENCIA_OBLIGATORIA",
    "COMBINACION_LOGICA",
    "AGREGACION_AMBITO",
)

# Escala de DECISION_ENGINE.md §3, sin inventar una nueva. NUNCA un número.
PRIORIDADES = ("bloqueante", "riesgo_variable", "recomendable", "preferencial")

# Aristas tipadas entre normas (`NORMATIVE_ENGINE.md` §9). Una lista de
# strings no sirve: las referencias son dirigidas, tipadas y con vigencia.
TIPOS_ARISTA = (
    "deroga", "modifica", "desarrolla", "endurece",
    "remite_a", "exime_de", "se_mide_segun", "corrige_erratum",
)

NIVELES_CONOCIMIENTO = (1, 2, 3, 4)


# --- NormaFuente ------------------------------------------------------------

@dataclass(frozen=True)
class Fuente:
    """Lo que convierte una cita en verificable.

    Sin `boletin` e `identificador_oficial` no hay NormaFuente, y sin
    NormaFuente no hay ReglaNormativa activable. Es lo que hace
    estructuralmente imposible que una etiqueta de agrupación
    (`HABITABILIDAD`, `EFICIENCIA`) se presente como código normativo, que es
    lo que hoy ocurre en `evaluator.py`.
    """

    rango: str                    # Ley / RD / Decreto / Orden / Ordenanza / Plan
    organismo: str
    identificador_oficial: str    # p. ej. "314/2006"
    titulo: str
    boletin: str                  # p. ej. "BOE-A-2006-5515"
    url_oficial: Optional[str] = None
    hash_texto: Optional[str] = None


@dataclass(frozen=True)
class Articulo:
    """Localizador jerárquico, no un string.

    Un string como "CTE DB-SUA-1" no permite ordenar, comparar, ni detectar
    que dos reglas citan el mismo apartado. Con `documento_basico` como valor
    de catálogo, la validación 12 puede comprobar que la materia declarada
    pertenece al ámbito de ese DB — el validador que habría impedido las 5
    discrepancias M1-M5 de la auditoría.
    """

    documento_basico: Optional[str] = None   # "DB-SUA" | None si no es CTE
    seccion: Optional[str] = None
    apartado: Optional[str] = None
    punto: Optional[str] = None
    tabla: Optional[str] = None

    def __str__(self) -> str:
        partes = [p for p in (self.documento_basico, self.seccion, self.apartado, self.punto) if p]
        return " ".join(partes) or "(sin localizar)"


@dataclass(frozen=True)
class Vigencia:
    """Bitemporal (`NORMATIVE_ENGINE.md` §4.1).

    - Eje legal: desde/hasta cuándo la norma estuvo en vigor.
    - Eje de registro: qué sabía ArchMuse el día que emitió un informe.

    El segundo es lo que convierte un informe en defendible tres años después.
    Es la diferencia entre una funcionalidad y un seguro.
    """

    vigencia_desde: date
    vigencia_hasta: Optional[date] = None
    registro_desde: Optional[date] = None
    registro_hasta: Optional[date] = None

    def vigente_en(self, fecha: date) -> bool:
        if fecha < self.vigencia_desde:
            return False
        return self.vigencia_hasta is None or fecha < self.vigencia_hasta

    def conocida_en(self, fecha: date) -> bool:
        """Si el registro estaba cargado en `fecha`. Sirve para reconstruir
        un informe pasado con el corpus que existía ese día, no con el de hoy."""
        if self.registro_desde and fecha < self.registro_desde:
            return False
        return self.registro_hasta is None or fecha < self.registro_hasta


@dataclass(frozen=True)
class NormaFuente:
    concept_id: str
    instance_id: str
    fuente: Fuente
    articulo: Articulo
    vigencia: Vigencia
    literal: str = ""              # transcripción exacta; inmutable
    ambito: str = "es"             # ruta de ámbito territorial


# --- Aplicabilidad ----------------------------------------------------------

@dataclass(frozen=True)
class Aplicabilidad:
    """Los tres ejes de filtrado de una regla.

    Una lista vacía significa "todos", nunca "ninguno". Es lo que evita que
    cada regla tenga que enumerar las 5 tipologías y los 7 tipos de
    intervención — la explosión combinatoria que este diseño existe para
    impedir.
    """

    ambito: str                                  # ruta: "es", "es.13", "es.13.28.28115"
    tipos_de_intervencion: Tuple[str, ...] = ()
    usos: Tuple[str, ...] = ()                   # nodo del árbol; cubre descendientes
    tipologias: Tuple[str, ...] = ()
    sectoriales: Tuple[str, ...] = ()            # exige que el sectorial esté declarado

    @property
    def nivel(self) -> str:
        """Nivel territorial deducido de la profundidad de la ruta.

        La profundidad es variable por diseño; lo que importa es cuántos
        segmentos con corpus tiene, no un número fijo de niveles.
        """
        n = self.ambito.count(".")
        if n == 0:
            return "estatal"
        if n == 1:
            return "autonomico"
        return "municipal"


# --- ReglaNormativa ---------------------------------------------------------

@dataclass(frozen=True)
class Parametro:
    """Un umbral NUNCA es un escalar (`CONSTRAINT_MODEL.md` §9).

    Siempre tabla indexada por ejes de contexto con cadena de repliegue
    explícita y ordenada. Cada vez que se usa un nivel de repliegue en lugar
    de una coincidencia exacta, ese hecho se escribe en la Evidence: un
    repliegue silencioso en materia autonómica es el Bug #1 reencarnado en la
    capa normativa.

    `repliegue` terminado en "ninguno" significa que si no hay valor, no hay
    valor: la regla queda `aplica_no_evaluable`, nunca coge un valor por
    defecto.
    """

    ejes: Tuple[str, ...]
    valores: Tuple[dict, ...]
    repliegue: Tuple[str, ...]
    unidad: Optional[str] = None

    def resolver(self, contexto: dict) -> Tuple[Optional[float], List[str]]:
        """Devuelve (valor, traza). La traza registra qué nivel de repliegue
        se usó — es lo que la Evidence tiene que mostrar."""
        traza: List[str] = []
        for nivel in self.repliegue:
            if nivel == "ninguno":
                traza.append("sin valor aplicable: la regla queda no evaluable")
                return None, traza
            ejes_activos = [e for e in self.ejes if e == nivel or nivel == "todos"]
            for v in self.valores:
                claves = {k: val for k, val in v.items() if k != "valor"}
                if not claves and nivel == "todos":
                    traza.append("valor por defecto de la tabla (sin ejes)")
                    return v["valor"], traza
                if claves and all(contexto.get(k) == val for k, val in claves.items()):
                    if set(claves) == set(ejes_activos) or nivel == "todos":
                        traza.append(f"coincidencia exacta por {sorted(claves)}")
                        return v["valor"], traza
            traza.append(f"sin valor para el eje «{nivel}»; se repliega")
        traza.append("cadena de repliegue agotada")
        return None, traza


@dataclass(frozen=True)
class Arista:
    tipo: str
    destino: str                   # concept_id
    vigencia: Optional[Vigencia] = None


@dataclass(frozen=True)
class ReglaNormativa:
    concept_id: str
    instance_id: str
    nombre: str
    materia: str
    tipo: str
    prioridad: str
    nivel_de_conocimiento: int
    aplicabilidad: Aplicabilidad
    norma: str                     # concept_id de la NormaFuente
    vigencia: Vigencia
    patron: Optional[str] = None
    parametro: Optional[Parametro] = None
    condiciones: Optional[dict] = None
    mensaje: str = ""
    explicacion_tecnica: str = ""
    explicacion_cliente: str = ""
    resumen_operativo: str = ""
    aristas: Tuple[Arista, ...] = ()
    # `tags` es libre PRECISAMENTE porque no decide nada. En cuanto un tag
    # influya en si una regla aplica, se habrá creado un eje de resolución sin
    # gobierno. El resolver no lee este campo.
    tags: Tuple[str, ...] = ()

    @property
    def evaluable(self) -> bool:
        return TIPOS_REGLA.get(self.tipo, False)
