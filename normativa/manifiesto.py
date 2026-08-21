"""Cobertura declarada por ámbito y materia.

**La cobertura no se infiere de la ausencia de reglas.** Que no haya reglas de
patrimonio cargadas para Pozuelo no significa que Pozuelo no tenga normativa
de patrimonio: significa que no la hemos transcrito. Confundir ambas cosas es
la inferencia negativa que `docs/brain/INFERENCE_ENGINE.md` §2.2 prohíbe — y
es la más peligrosa del sistema, porque falla como un tranquilizador "no hay
problemas".

Por eso la cobertura es un dato declarado (`normativa/cobertura/manifiesto.yaml`)
y no una consulta al corpus. La diferencia entre estas dos frases es la
diferencia entre un producto insostenible y uno vendible:

    "Tu proyecto cumple."
    "Tu proyecto cumple las 214 reglas cargadas para Pozuelo de Alarcón.
     No hay cobertura de patrimonio ni de medio ambiente."
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

from . import catalogos
from .ambito import CadenaAmbitos

MANIFIESTO = Path(__file__).resolve().parent / "cobertura" / "manifiesto.yaml"

# `no_competente` es el tercer estado, y no es obvio: distingue "no lo tenemos"
# de "aquí no hay nada que tener porque la materia es de otro nivel". Sin él,
# todo municipio aparecería eternamente incompleto en materias que nunca le
# corresponden.
#
# `transcrito_sin_firmar` es el quinto, y es el estado en el que vive TODA regla
# entre que el curador la transcribe y queda confirmada — o sea, el estado
# normal durante todo el trabajo que queda por delante. Existe porque los cuatro
# anteriores obligaban a mentir en uno de los dos sentidos: `ausente` niega un
# trabajo que está hecho y en disco, y `parcial` es **afirmable**, de modo que
# ArchMuse pasaría a evaluar seguridad contra incendios con una regla que nadie
# ha revisado. Ninguna de las dos es la verdad, y la verdad aquí es barata de
# decir. No es afirmable a propósito: el trabajo transcrito cuenta como
# progreso, no como respaldo.
#
# Hasta el Prompt 2 (docs/prd/2026-08-21-verificacion-doble-del-corpus.md
# §5.6) este estado lo escribía a mano el curador en
# `normativa/cobertura/manifiesto.yaml`, y solo la validación 18 impedía que
# mintiera. Desde entonces se DERIVA mecánicamente del estado real de las
# reglas (`cobertura()` + `estado_derivado()`, más abajo): una materia con
# alguna regla `BORRADOR`, o histórica con el tag `pendiente_firma_colegiado`,
# nunca sale `completo`/`parcial` aunque el fichero lo declare así — la firma
# de colegiado que el nombre evoca ya no es el mecanismo (ese concepto se
# abandonó, docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md §9);
# ahora "confirmada" es `VERIFICADA_AUTOMATICA`/`FIRMADA` a nivel de regla
# individual (`normativa/resolucion.py`). El nombre del estado se conserva
# porque el significado —hay trabajo en disco que aún no se puede afirmar— es
# el mismo.
ESTADOS = ("completo", "parcial", "transcrito_sin_firmar", "ausente", "no_competente")

#: Los estados que afirman que hay reglas de esa materia EN DISCO. La
#: validación 17 los exige respaldados por ficheros reales; los otros dos
#: (`ausente`, `no_competente`) declaran justo lo contrario.
ESTADOS_CON_REGLAS = ("completo", "parcial", "transcrito_sin_firmar")


@dataclass
class EntradaCobertura:
    ambito: str
    materia: str
    estado: str
    verificado: Optional[str] = None
    por: Optional[str] = None

    @property
    def afirmable(self) -> bool:
        """Si se puede afirmar algo sobre esta materia en este ámbito.

        `transcrito_sin_firmar` **no** lo es, y esa es toda la utilidad del
        estado: una regla transcrita y sin revisar es trabajo adelantado, no
        respaldo. Afirmar sobre ella sería exactamente lo que el producto
        entero existe para no hacer.
        """
        return self.estado in ("completo", "parcial")

    @property
    def transcrito_sin_firmar(self) -> bool:
        return self.estado == "transcrito_sin_firmar"


@dataclass
class InformeCobertura:
    entradas: List[EntradaCobertura] = field(default_factory=list)
    # Materias que existen en disco pero cuyo fichero fue rechazado en carga:
    # hay corpus y está roto, que es peor que no tenerlo y se dice igual.
    rotas: List[str] = field(default_factory=list)

    def sin_cobertura(self) -> List[EntradaCobertura]:
        return [e for e in self.entradas if e.estado == "ausente"]

    def afirmables(self) -> List[EntradaCobertura]:
        return [e for e in self.entradas if e.afirmable]

    def transcritas_sin_firmar(self) -> List[EntradaCobertura]:
        """Materias con reglas en disco que ningún colegiado ha firmado."""
        return [e for e in self.entradas if e.transcrito_sin_firmar]

    def resumen(self) -> str:
        """Frase que el producto debe mostrar. Nunca "cumple" a secas."""
        ok = self.afirmables()
        falta = self.sin_cobertura()
        sin_firma = self.transcritas_sin_firmar()
        partes = []
        if ok:
            partes.append("Cobertura: " + " · ".join(f"{e.materia} ({e.estado})" for e in ok))
        if sin_firma:
            # Va en su propia frase y no junto a la cobertura: leerlo como
            # cobertura es el error que este estado existe para impedir.
            partes.append(
                "Transcrito pero sin firma de colegiado, no se afirma sobre ello: "
                + ", ".join(e.materia for e in sin_firma))
        if falta:
            partes.append("Sin cobertura de " + ", ".join(e.materia for e in falta))
        if self.rotas:
            partes.append("Corpus no cargable en " + ", ".join(self.rotas))
        return ". ".join(partes) if partes else "Sin cobertura declarada para este ámbito."

    def a_dict(self) -> dict:
        return {
            "entradas": [
                {
                    "ambito": e.ambito,
                    "materia": e.materia,
                    "estado": e.estado,
                    "verificado": e.verificado,
                }
                for e in self.entradas
            ],
            "rotas": list(self.rotas),
            "resumen": self.resumen(),
        }


def _regla_confirmada(regla: dict) -> bool:
    """Afirmable a nivel de UNA regla — el mismo criterio, palabra por
    palabra, que `normativa/resolucion.py::_paso1_candidatas`. Se duplica la
    lógica (no se importa) porque `resolucion.py` importa este módulo y un
    import en sentido contrario crearía un ciclo; que no diverjan depende de
    `tests/test_normativa_manifiesto_deriva.py`, que las compara.
    """
    estado = regla.get("estado")
    if estado in ("VERIFICADA_AUTOMATICA", "FIRMADA"):
        return True
    if estado is not None:
        return False  # BORRADOR, o cualquier estado futuro no afirmable
    # Regla histórica, anterior al campo `estado` (p. ej. seguridad_incendio.yaml):
    # la gobierna el tag legado, como hacía la validación 18 antes de esto.
    # Import local a propósito: `validacion` importa de este módulo a nivel de
    # módulo (`ESTADOS_CON_REGLAS`), así que un `import` al principio de este
    # fichero crearía un ciclo que revienta según quién se importe primero.
    from . import validacion
    return validacion.TAG_SIN_FIRMAR not in (regla.get("tags") or [])


def estado_derivado(declarado: Optional[str], reglas: List[dict]) -> str:
    """El estado real de una materia en un ámbito, mirando sus reglas — no
    la cadena que alguien escribió a mano en `manifiesto.yaml`.

    Decisión de Pablo (2026-08-21, Prompt 1 §9, ejecutada en el Prompt 2
    §5.6): una materia es `completo`/`parcial` **solo** cuando TODAS sus
    reglas activas son `VERIFICADA_AUTOMATICA` o `FIRMADA` — nunca si queda
    alguna `BORRADOR` o sin confirmar, aunque el fichero declare lo
    contrario. Sustituye la promoción manual de `transcrito_sin_firmar`.

    - Sin reglas en disco y lo declarado no promete reglas (`ausente`,
      `no_competente`, o nada): se respeta tal cual, no hay nada que derivar.
    - Sin reglas en disco pero lo declarado SÍ promete reglas (`completo`,
      `parcial` o `transcrito_sin_firmar`, es decir `ESTADOS_CON_REGLAS`):
      no se confía a ciegas — es la misma mentira que la validación 17
      rechaza al cargar, y aquí no hay corpus detrás para comprobarla. Se
      fuerza a `ausente`.
    - Con reglas, todas confirmadas: si ya se declaraba `completo` o
      `parcial`, se mantiene (la EXTENSIÓN de la materia — si es todo el DB
      o solo un apartado — no se puede derivar del estado de la regla, así
      que no se inventa); si no, se sube a `parcial` por defecto, nunca a
      `completo` sin que un humano lo haya declarado así.
    - Con reglas, alguna sin confirmar: `transcrito_sin_firmar`, siempre,
      pisando lo declarado — es exactamente el caso que este mecanismo
      existe para no dejar mentir.
    """
    if not reglas:
        if declarado in ESTADOS_CON_REGLAS:
            return "ausente"
        return declarado or "ausente"
    if all(_regla_confirmada(r) for r in reglas):
        return declarado if declarado in ("completo", "parcial") else "parcial"
    return "transcrito_sin_firmar"


@functools.lru_cache(maxsize=4)
def _manifiesto(ruta: Optional[Path] = None) -> dict:
    """Cacheado POR RUTA, no globalmente. La lección es de la Fase 0: un
    `lru_cache(maxsize=1)` sobre una función con argumento opcional construyó
    dos registros geográficos porque `f()` y `f("es")` son claves distintas."""
    ruta = ruta or MANIFIESTO
    if not ruta.exists():
        return {"cobertura": []}
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {"cobertura": []}


def _declarado(ruta: Optional[Path] = None) -> Dict[str, Dict[str, dict]]:
    salida: Dict[str, Dict[str, dict]] = {}
    for e in _manifiesto(ruta).get("cobertura") or []:
        salida[e["ambito"]] = e.get("materias") or {}
    return salida


def cobertura(
    cadena: CadenaAmbitos,
    rotas: Optional[Set[str]] = None,
    ruta: Optional[Path] = None,
    reglas_por_ambito_materia: Optional[Dict[Tuple[str, str], List[dict]]] = None,
) -> InformeCobertura:
    """Informe de cobertura de una cadena territorial.

    Recorre TODAS las materias del catálogo, no solo las declaradas: una
    materia sobre la que el manifiesto calla es `ausente`, y eso hay que
    decirlo. El silencio no es cobertura.

    `reglas_por_ambito_materia` es opcional a propósito (compatibilidad con
    quien todavía no lo pase), pero en producción SIEMPRE llega poblado
    (`normativa/api.py::cobertura()`, `normativa/resolucion.py::_resolver`):
    es lo que permite derivar `completo`/`parcial`/`transcrito_sin_firmar`
    del estado real de las reglas en vez de confiar en la cadena que alguien
    escribió en `manifiesto.yaml` (`estado_derivado()`, arriba).
    """
    declarado = _declarado(ruta)
    reglas_por_ambito_materia = reglas_por_ambito_materia or {}
    comps = catalogos.competencias()
    entradas: List[EntradaCobertura] = []

    for materia in catalogos.materias():
        comp = comps.get(materia, {})
        nivel_competente = comp.get("competencia")

        # ¿Qué ámbito de la cadena es el competente para esta materia?
        ambito_obj = None
        if nivel_competente == "sectorial":
            # Los sectoriales no son un nivel de la cadena: la atraviesan
            # (§3.3), así que ningún ámbito tiene nivel "sectorial" y buscarlo
            # por nivel no encontraría nunca nada — dejando patrimonio y medio
            # ambiente eternamente "ausentes" aunque estuvieran transcritos.
            # Su corpus vive, de hecho, en el ámbito territorial más concreto
            # con corpus (el esquema ni siquiera admite una ruta de ámbito
            # sectorial), y ahí es donde se declara su cobertura.
            ambito_obj = next(
                (a for a in reversed(cadena.ambitos) if a.tiene_corpus), None
            )
        else:
            for a in cadena.ambitos:
                if not a.tiene_corpus:
                    continue
                if catalogos.nivel_de_ambito(a.id) == nivel_competente:
                    ambito_obj = a
                    break

        if ambito_obj is None:
            # La cadena no llega al nivel competente (p. ej. no se declaró
            # municipio y la materia es municipal). No es "ausente": es que no
            # se ha preguntado por ese nivel.
            entradas.append(
                EntradaCobertura(
                    ambito=cadena.mas_especifico.id,
                    materia=materia,
                    estado="ausente" if nivel_competente else "no_competente",
                )
            )
            continue

        decl = declarado.get(ambito_obj.id, {}).get(materia)
        reglas = reglas_por_ambito_materia.get((ambito_obj.id, materia), [])

        if decl is None and not reglas:
            entradas.append(EntradaCobertura(ambito_obj.id, materia, "ausente"))
            continue

        estado_declarado = decl.get("estado") if isinstance(decl, dict) else (
            str(decl) if decl is not None else None
        )
        estado = estado_derivado(estado_declarado, reglas)
        entradas.append(
            EntradaCobertura(
                ambito=ambito_obj.id,
                materia=materia,
                estado=estado if estado in ESTADOS else "ausente",
                verificado=(decl.get("verificado") if isinstance(decl, dict) else None),
                por=(decl.get("por") if isinstance(decl, dict) else None),
            )
        )

    return InformeCobertura(entradas=entradas, rotas=sorted(rotas or set()))
