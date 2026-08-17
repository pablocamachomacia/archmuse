"""Carga del corpus: descubrir -> parsear -> validar -> indexar.

Dos decisiones gobiernan este módulo (`NORMATIVE_RESOLUTION.md` §8.1):

**Fail-closed.** Si un fichero no valida, el sistema NO carga "lo que sí
funciona": marca esa materia de ese ámbito como `sin_cobertura` y lo dice. La
alternativa —cargar parcialmente— produce el peor resultado posible: un
informe que afirma cumplimiento sobre un corpus mutilado sin que nadie lo sepa.

**Carga perezosa por ámbito.** No se carga el corpus: se carga la cadena del
proyecto. Para Pozuelo son 3 ámbitos con corpus (estatal, comunidad,
municipio), del orden de 5-15 ficheros. **El coste de carga es independiente
del tamaño total del corpus** — la propiedad sin la cual 8.131 municipios sí
serían un problema.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import yaml

from . import validacion
from .ambito import CadenaAmbitos

RAIZ = Path(__file__).resolve().parent

# Subdirectorios de datos. Ninguno puede contener un `.py`: es la frontera F2
# de `NORMATIVE_RESOLUTION.md` §2 (la capa de datos no contiene lógica), y hay
# un test que la comprueba.
DIRECTORIOS_DE_DATOS = ("esquema", "geografia", "es", "sectorial", "cobertura", "terminologia")


@dataclass
class FicheroCorpus:
    ruta: Path
    ambito: str
    doc: dict
    materias: Set[str] = field(default_factory=set)


@dataclass
class ResultadoCarga:
    """Lo cargado y —tan importante como eso— lo rechazado y por qué.

    `rechazados` no es una lista de errores para el log: es lo que alimenta el
    estado `sin_cobertura`. Un fichero rechazado significa que esa materia de
    ese ámbito no se puede afirmar, y el informe tiene que decirlo.
    """

    ficheros: List[FicheroCorpus] = field(default_factory=list)
    rechazados: Dict[str, List[str]] = field(default_factory=dict)
    materias_por_ambito: Dict[str, Set[str]] = field(default_factory=dict)
    raiz: Path = RAIZ

    @property
    def reglas(self) -> List[dict]:
        return [r for f in self.ficheros for r in (f.doc.get("reglas") or [])]

    @property
    def hay_rechazos(self) -> bool:
        return bool(self.rechazados)

    def materias_sin_cobertura_por_fallo(self) -> Set[Tuple[str, str]]:
        """(ámbito, materia) que existían en disco pero no se han podido
        cargar. Distinto de "no hay corpus": aquí lo hay y está roto, que es
        peor y hay que decirlo igual."""
        fuera: Set[Tuple[str, str]] = set()
        for ruta in self.rechazados:
            p = Path(ruta)
            fuera.add((_ambito_de_ruta(p, self.raiz), p.stem))
        return fuera


def normalizar_fechas(valor):
    """Convierte `date`/`datetime` a cadena ISO, recursivamente.

    PyYAML interpreta `2000-01-01` sin comillas como un `datetime.date`. El
    esquema espera cadenas, así que sin esta normalización el primer fichero
    de corpus real habría fallado la validación por un motivo que no tiene
    nada que ver con su contenido — y la salida natural habría sido obligar al
    curador a entrecomillar todas las fechas, que es pedirle que recuerde una
    regla arbitraria a cambio de nada.

    Se normaliza al cargar, antes de validar: el curador escribe la fecha como
    quiera y el sistema se entiende consigo mismo.
    """
    from datetime import date as _date, datetime as _datetime

    if isinstance(valor, _datetime):
        return valor.date().isoformat()
    if isinstance(valor, _date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: normalizar_fechas(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [normalizar_fechas(v) for v in valor]
    return valor


def _ambito_de_ruta(ruta: Path, raiz: Optional[Path] = None) -> str:
    """Deduce la ruta de ámbito desde la ubicación del fichero en el árbol.

    `normativa/es/estatal/...`            -> es
    `normativa/es/13-madrid/...`          -> es.13
    `normativa/es/13-madrid/municipios/28115-pozuelo/...` -> es.13.28115

    El directorio lleva código y slug (`28115-pozuelo-de-alarcon`): el código
    es la identidad, el slug es para el humano que navega el repositorio. Si
    el nombre oficial cambia, se renombra el directorio y nada se rompe,
    porque nada resuelve por nombre de directorio.
    """
    try:
        partes = ruta.relative_to(raiz or RAIZ).parts
    except ValueError:
        return "es"
    if not partes:
        return "es"
    pais = partes[0]
    if len(partes) < 2 or partes[1] == "estatal":
        return pais
    codigo_com = partes[1].split("-")[0]
    if "municipios" in partes:
        i = partes.index("municipios")
        if i + 1 < len(partes):
            codigo_muni = partes[i + 1].split("-")[0]
            # El árbol no tiene nivel de provincia (ninguna regula edificación,
            # ver NORMATIVE_RESOLUTION.md §6), pero la ruta de ámbito sí lo
            # lleva. Se deriva del propio código INE del municipio, cuyos dos
            # primeros dígitos SON la provincia — por eso la identidad es el
            # código y no el nombre: el código contiene su jerarquía.
            return f"{pais}.{codigo_com}.{codigo_muni[:2]}.{codigo_muni}"
    return f"{pais}.{codigo_com}"


def _directorios_de_ambito(ambito_id: str, raiz: Optional[Path] = None) -> List[Path]:
    """Directorios en disco que contienen el corpus de un ámbito."""
    partes = ambito_id.split(".")
    pais = partes[0]
    base = (raiz or RAIZ) / pais
    if len(partes) == 1:
        return [base / "estatal"]
    com = _buscar_por_codigo(base, partes[1])
    if com is None:
        return []
    if len(partes) == 2:
        return [d for d in com.iterdir() if d.is_dir() and d.name != "municipios"]
    muni = _buscar_por_codigo(com / "municipios", partes[-1])
    return [muni] if muni else []


def _buscar_por_codigo(base: Path, codigo: str) -> Optional[Path]:
    """Encuentra `28115-pozuelo-de-alarcon` dado `28115`. La identidad es el
    código; el slug puede cambiar sin consecuencias."""
    if not base.is_dir():
        return None
    for d in base.iterdir():
        if d.is_dir() and d.name.split("-")[0] == codigo:
            return d
    return None


def descubrir(ambitos: Iterable[str], raiz: Optional[Path] = None) -> List[Path]:
    """Ficheros YAML de corpus de los ámbitos dados. Solo estos se abren:
    es la carga perezosa.

    `raiz` existe para poder ejercitar el resolver contra un corpus de prueba
    sin meter reglas ficticias en el corpus real. No es un punto de extensión:
    en producción nadie lo pasa, y el corpus de verdad vive en un solo sitio.
    """
    rutas: List[Path] = []
    for a in ambitos:
        for d in _directorios_de_ambito(a, raiz):
            if d.is_dir():
                rutas.extend(sorted(p for p in d.rglob("*.yaml") if not p.name.startswith("_")))
    return rutas


def cargar(ambitos: Iterable[str], raiz: Optional[Path] = None) -> ResultadoCarga:
    """Carga y valida el corpus de `ambitos`. Fail-closed por fichero.

    Un fichero inválido no aborta la carga entera —eso dejaría al usuario sin
    nada— pero tampoco entra: queda registrado en `rechazados` y su materia
    pasa a `sin_cobertura`. Es la única forma de que un corpus roto se note
    en el informe en vez de desaparecer.
    """
    resultado = ResultadoCarga(raiz=raiz or RAIZ)
    docs_validos: List[dict] = []

    for ruta in descubrir(ambitos, raiz):
        try:
            with ruta.open(encoding="utf-8") as f:
                doc = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as exc:
            resultado.rechazados[str(ruta)] = [f"[0] no se puede leer: {exc}"]
            continue

        if not isinstance(doc, dict):
            resultado.rechazados[str(ruta)] = ["[0] el fichero no contiene un mapa en su raíz"]
            continue

        doc = normalizar_fechas(doc)
        fallos = validacion.validar_fichero(doc)
        if fallos:
            resultado.rechazados[str(ruta)] = fallos
            continue

        ambito = _ambito_de_ruta(ruta, raiz)
        materias = {r.get("materia") for r in (doc.get("reglas") or []) if r.get("materia")}
        resultado.ficheros.append(FicheroCorpus(ruta=ruta, ambito=ambito, doc=doc, materias=materias))
        resultado.materias_por_ambito.setdefault(ambito, set()).update(materias)
        docs_validos.append(doc)

    # Validaciones que necesitan ver el conjunto (aristas, contradicciones).
    # Un fallo aquí invalida el corpus cargado, no un fichero: no se puede
    # decidir cuál de los dos sobra sin tomar una decisión que no nos toca.
    fallos_globales = validacion.validar_corpus(docs_validos)
    if fallos_globales:
        resultado.rechazados["(corpus completo)"] = fallos_globales
        resultado.ficheros.clear()
        resultado.materias_por_ambito.clear()

    return resultado


def cargar_cadena(cadena: CadenaAmbitos, raiz: Optional[Path] = None) -> ResultadoCarga:
    """Carga el corpus de una cadena territorial resuelta."""
    return cargar(cadena.ids_con_corpus, raiz)


def huella_corpus() -> str:
    """Hash del corpus entero, para sellar el índice derivado.

    Si no coincide con el sellado, el índice se regenera. El índice es caché,
    nunca fuente de verdad (`NORMATIVE_ENGINE.md` §11): se puede borrar.
    """
    h = hashlib.sha256()
    for p in sorted((RAIZ).rglob("*.yaml")):
        h.update(p.relative_to(RAIZ).as_posix().encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()
