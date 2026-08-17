"""Superficie pública del subsistema normativo.

**Esto es todo lo que el resto del sistema puede llamar.** Loader, índice,
validadores, registro y catálogos son privados: si algo fuera del paquete
necesita leerlos, la frontera está mal puesta.

Reglas del contrato (`NORMATIVE_RESOLUTION.md` §11):

- **Todo es puro y sin estado.** Mismas entradas, mismo resultado, siempre.
  Es requisito de la traza reproducible de `TRACEABILITY.md` §10.
- **`normativa/` no importa nada de `analyzer/`.** La dependencia va en un
  solo sentido, y hay un test que falla si se invierte. Este paquete se
  prueba entero sin un DXF.
- **`fecha_devengo=None` no es "hoy" en silencio**: se usa hoy y se devuelve
  la asunción, que quien la consuma está obligado a mostrar.

ESTADO — FASES 0 y 1. Implementadas la resolución territorial, el perfil de
proyecto, la carga, la validación, la cobertura y `normativa_aplicable()` (el
motor de resolución completo, los ocho pasos de `NORMATIVE_RESOLUTION.md`
§7.3). `explicar_aplicabilidad()` y `diff_normativo()` son de las Fases 3 y 6:
se declaran aquí para fijar el contrato y levantan `NotImplementedError` en vez
de devolver un resultado incompleto que parecería válido.

**El corpus sigue vacío**, y eso no es un defecto del motor: transcribir
normativa exige validación de un arquitecto colegiado (tarea 18 del PRD). El
motor resuelve correctamente que, para cualquier proyecto, falta TODA la
normativa exigible — y lo dice con nombre y apellidos en vez de devolver una
lista corta que se leería como completa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import catalogos, derivados
from .ambito import Ambito, AmbitoSectorial, CadenaAmbitos, Procedencia
from .manifiesto import InformeCobertura, cobertura as _cobertura
from .errores import (
    AmbitoAmbiguo,
    AmbitoDesconocido,
    CoberturaInsuficiente,
    CorpusInvalido,
    ErrorNormativa,
    RegistroIncompleto,
)
from .loader import ResultadoCarga, cargar_cadena
from .registro import resolver_ambito as _resolver_ambito
from .resolucion import (
    Conflicto,
    ConjuntoAplicable,
    FuenteOficial,
    MateriaFaltante,
    NormaAplicable,
    Relacion,
    resolver as _resolver,
)

__all__ = [
    "resolver_ambito",
    "perfil_proyecto",
    "cobertura",
    "contexto_territorial",
    "normativa_aplicable",
    "explicar_aplicabilidad",
    "diff_normativo",
    "PerfilProyecto",
    "ContextoTerritorial",
    "CadenaAmbitos",
    "Ambito",
    "AmbitoSectorial",
    "InformeCobertura",
    "ConjuntoAplicable",
    "NormaAplicable",
    "FuenteOficial",
    "Relacion",
    "Conflicto",
    "MateriaFaltante",
    "AmbitoAmbiguo",
    "AmbitoDesconocido",
    "CoberturaInsuficiente",
    "CorpusInvalido",
    "ErrorNormativa",
    "RegistroIncompleto",
]


# --- Perfil de proyecto -----------------------------------------------------

@dataclass(frozen=True)
class PerfilProyecto:
    """Segundo eje de filtrado, ortogonal al territorial.

    `usos_presentes` existe porque **el uso es por pieza, no solo por
    edificio**: un edificio residencial con local comercial en planta baja
    tiene dos usos simultáneos, y las reglas de pública concurrencia aplican
    al local aunque el edificio sea residencial. Diseñarlo con un solo uso
    ahorra dos días ahora y obliga a rehacerlo entero al primer proyecto de
    uso mixto.

    `asunciones` nunca va vacía por comodidad: si se ha traducido un valor
    heredado de `evaluator.UMBRALES_TIPOLOGIA`, aquí queda dicho. Quien
    consuma el perfil está obligado a mostrarlo — una suposición no se
    convierte en hecho callando (`UNCERTAINTY_MODEL.md`).
    """

    tipo_de_intervencion: str
    uso_principal: str
    tipologia: str
    usos_presentes: Tuple[str, ...] = ()
    asunciones: Tuple[str, ...] = ()

    def cubre_uso(self, uso_declarado_en_regla: str) -> bool:
        return any(
            catalogos.uso_cubre(uso_declarado_en_regla, u)
            for u in (self.usos_presentes or (self.uso_principal,))
        )


def perfil_proyecto(
    tipo_de_intervencion: Optional[str] = None,
    uso: Optional[str] = None,
    tipologia: Optional[str] = None,
    usos_presentes: Optional[List[str]] = None,
) -> PerfilProyecto:
    """Construye el perfil, traduciendo los valores heredados de
    `evaluator.UMBRALES_TIPOLOGIA` y declarando cada asunción.

    Los tres valores que `evaluator.py` maneja hoy ("plurifamiliar",
    "unifamiliar", "rehabilitacion") mezclan dos ejes: `rehabilitacion` es un
    tipo de intervención, no una tipología. Se traducen, nunca en silencio.
    """
    asunciones: List[str] = []
    equivalencias = catalogos.equivalencias_heredadas()

    if tipologia in equivalencias:
        eq = equivalencias[tipologia]
        asunciones.append(eq["asuncion"].strip())
        tipo_de_intervencion = tipo_de_intervencion or eq["tipo_de_intervencion"]
        tipologia = eq["tipologia"]

    if not tipologia:
        raise ValueError("perfil_proyecto: falta la tipología")
    if tipologia not in catalogos.tipologias():
        raise ValueError(f"Tipología desconocida: «{tipologia}»")

    tipo_de_intervencion = tipo_de_intervencion or "obra_nueva"
    if tipo_de_intervencion not in catalogos.tipos_de_intervencion():
        raise ValueError(f"Tipo de intervención desconocido: «{tipo_de_intervencion}»")

    uso = uso or "residencial.vivienda_libre"
    if uso not in catalogos.usos():
        raise ValueError(f"Uso desconocido: «{uso}»")

    presentes = tuple(usos_presentes or (uso,))
    for u in presentes:
        if u not in catalogos.usos():
            raise ValueError(f"Uso desconocido: «{u}»")

    return PerfilProyecto(
        tipo_de_intervencion=tipo_de_intervencion,
        uso_principal=uso,
        tipologia=tipologia,
        usos_presentes=presentes,
        asunciones=tuple(asunciones),
    )


# --- Contexto territorial ---------------------------------------------------

@dataclass(frozen=True)
class ContextoTerritorial:
    """Todo lo que el territorio aporta a un análisis, en un solo objeto.

    Es lo que `app.py` construye una vez y pasa hacia abajo. Los ejes de
    contexto (zona climática, densidad, comunidad, municipio) salen de aquí,
    de una única lista de municipios, en vez de tres tablas paralelas.
    """

    cadena: CadenaAmbitos
    perfil: PerfilProyecto
    fecha_devengo: date
    zona_climatica: Optional[str] = None
    densidad_urbana: Optional[str] = None
    asunciones: Tuple[str, ...] = ()

    @property
    def comunidad(self) -> Optional[Ambito]:
        return self.cadena.por_nivel("autonomico")

    @property
    def municipio(self) -> Optional[Ambito]:
        return self.cadena.por_nivel("municipal")

    def ejes_de_contexto(self) -> Dict[str, Optional[str]]:
        """Diccionario de ejes tal como lo consumen las tablas de parámetros
        de `CONSTRAINT_MODEL.md` §9. Ninguno se inventa: los desconocidos van
        como None y la cadena de repliegue decide, dejando traza."""
        return {
            "comunidad": self.comunidad.codigo if self.comunidad else None,
            "municipio": self.municipio.codigo if self.municipio else None,
            "zona_cte": self.zona_climatica,
            "densidad_urbana": self.densidad_urbana,
            "tipologia": self.perfil.tipologia,
            "tipo_de_intervencion": self.perfil.tipo_de_intervencion,
            "uso": self.perfil.uso_principal,
        }


def resolver_ambito(
    pais: str = "es",
    comunidad: Optional[str] = None,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    sectoriales: Optional[Dict[str, Optional[bool]]] = None,
) -> CadenaAmbitos:
    """Nombres o códigos -> cadena territorial. Ver `registro.resolver_ambito`."""
    return _resolver_ambito(pais, comunidad, provincia, municipio, sectoriales)


def contexto_territorial(
    pais: str = "es",
    comunidad: Optional[str] = None,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo_de_intervencion: Optional[str] = None,
    uso: Optional[str] = None,
    tipologia: Optional[str] = None,
    usos_presentes: Optional[List[str]] = None,
    fecha_devengo: Optional[date] = None,
    sectoriales: Optional[Dict[str, Optional[bool]]] = None,
) -> ContextoTerritorial:
    """Punto de entrada único: de lo que declara el usuario al contexto completo.

    `fecha_devengo=None` usa hoy **y lo declara como asunción**. La normativa
    aplicable a un proyecto no es la vigente hoy: es la vigente en su fecha de
    devengo, típicamente la de solicitud de licencia. Asumirla sin decirlo
    convertiría una suposición en hecho.
    """
    cadena = resolver_ambito(pais, comunidad, provincia, municipio, sectoriales)
    perfil = perfil_proyecto(tipo_de_intervencion, uso, tipologia, usos_presentes)
    return _contexto_desde_cadena(cadena, perfil, fecha_devengo)


def _contexto_desde_cadena(
    cadena: CadenaAmbitos, perfil: PerfilProyecto, fecha_devengo: Optional[date]
) -> ContextoTerritorial:
    """Deriva los ejes de contexto de una cadena y un perfil ya resueltos.

    Existe para que `contexto_territorial()` y `normativa_aplicable()` deriven
    la zona climática, la densidad y las asunciones por el MISMO camino. Dos
    caminos para lo mismo es como se acaba con una asunción declarada en una
    entrada del sistema y callada en la otra.
    """
    asunciones: List[str] = list(perfil.asunciones)
    if fecha_devengo is None:
        fecha_devengo = date.today()
        asunciones.append(
            "No se ha declarado fecha de devengo (solicitud de licencia): se ha "
            f"usado la de hoy, {fecha_devengo.isoformat()}. Un proyecto con "
            "licencia anterior se rige por la normativa vigente entonces."
        )

    muni = cadena.por_nivel("municipal")
    zona = derivados.zona_climatica(muni.codigo) if muni else None
    dens = derivados.densidad_urbana(muni.codigo) if muni else None
    if muni and zona is None:
        asunciones.append(
            f"No se conoce la zona climática de {muni.nombre}: las reglas que "
            "dependan de ella quedarán sin evaluar, no se replegarán a un valor."
        )
    if cadena.procedencia and not cadena.procedencia.verificado:
        asunciones.append(
            "El registro geográfico es una semilla manual sin verificar contra "
            "el fichero oficial del INE (ver normativa/geografia/es/_registro.yaml)."
        )

    return ContextoTerritorial(
        cadena=cadena,
        perfil=perfil,
        fecha_devengo=fecha_devengo,
        zona_climatica=zona,
        densidad_urbana=dens,
        asunciones=tuple(asunciones),
    )


# --- Cobertura --------------------------------------------------------------

def cobertura(cadena: CadenaAmbitos, fecha: Optional[date] = None) -> InformeCobertura:
    """Qué materias hay cargadas para esta cadena, y cuáles faltan.

    Un `ConjuntoAplicable` sin informe de cobertura no se puede interpretar:
    12 reglas cumplidas no significan nada si no se sabe sobre cuántas
    materias.
    """
    carga: ResultadoCarga = cargar_cadena(cadena)
    rotas = {materia for _, materia in carga.materias_sin_cobertura_por_fallo()}
    return _cobertura(cadena, rotas=rotas)


# --- Fases 1 y 6: contrato declarado, sin implementar -----------------------

def normativa_aplicable(
    contexto,
    perfil: Optional[PerfilProyecto] = None,
    fecha_devengo: Optional[date] = None,
    hechos: Optional[Dict[str, object]] = None,
    fecha_de_registro: Optional[date] = None,
    estricto: bool = True,
    raiz_corpus: Optional[Path] = None,
    ruta_manifiesto: Optional[Path] = None,
) -> ConjuntoAplicable:
    """FASE 1. Toda la normativa aplicable a un proyecto, en orden y con motivo.

    `contexto` es un `ContextoTerritorial` (forma recomendada: ya trae fecha de
    devengo, ejes y asunciones) o una `CadenaAmbitos`, en cuyo caso hay que
    pasar `perfil`.

    Devuelve un `ConjuntoAplicable`: cada regla candidata con uno de los cuatro
    estados de `NORMATIVE_RESOLUTION.md` §8.2 —`aplica`, `no_aplica` (siempre
    con motivo), `aplica_no_evaluable`, `sin_cobertura`— más el informe de
    cobertura, los conflictos sin resolver y las preguntas pendientes.

    **Fail-closed (`estricto=True`, el valor por defecto).** Si falta cobertura
    de alguna materia exigible a este proyecto, levanta `CoberturaInsuficiente`
    enumerando exactamente cuál falta, en qué ámbito y por qué se le exige. NO
    devuelve la parte que sí tenemos: una lista de normativa se lee como
    completa, siempre.

    `estricto=False` devuelve el conjunto con `completo=False` y `.faltantes`
    poblado. Es para una interfaz que quiera pintar el hueco, nunca para
    seguir calculando como si no existiera.

    Con el corpus actual (vacío) esta función levanta `CoberturaInsuficiente`
    para cualquier proyecto. Es el comportamiento correcto, no un fallo: la
    transcripción del corpus es la tarea 18 del PRD y necesita validación
    colegiada.
    """
    if isinstance(contexto, ContextoTerritorial):
        ctx = contexto
        if perfil is not None and perfil != ctx.perfil:
            raise ValueError(
                "Se ha pasado un ContextoTerritorial y además un perfil distinto: "
                "el contexto ya lleva el suyo y no se puede saber cuál manda."
            )
    else:
        if perfil is None:
            raise ValueError("normativa_aplicable: con una CadenaAmbitos hace falta el perfil")
        ctx = _contexto_desde_cadena(contexto, perfil, fecha_devengo)

    if fecha_devengo is not None and fecha_devengo != ctx.fecha_devengo:
        raise ValueError(
            f"fecha_devengo={fecha_devengo} contradice la del contexto "
            f"({ctx.fecha_devengo}). No se elige una en silencio."
        )

    return _resolver(
        cadena=ctx.cadena,
        perfil=ctx.perfil,
        fecha_devengo=ctx.fecha_devengo,
        ejes_contexto=ctx.ejes_de_contexto(),
        hechos=hechos,
        fecha_de_registro=fecha_de_registro,
        raiz_corpus=raiz_corpus,
        ruta_manifiesto=ruta_manifiesto,
        estricto=estricto,
        asunciones=ctx.asunciones,
    )


def explicar_aplicabilidad(concept_id, cadena, perfil, fecha=None):
    """FASE 3. Cadena causal de por qué una regla aplica o no aplica."""
    raise NotImplementedError("Fase 3 del PRD 2026-08-06-motor-de-normativa-territorial.")


def diff_normativo(cadena, perfil, fecha_a, fecha_b):
    """FASE 6. Qué cambió entre dos fechas y cómo afecta a este proyecto."""
    raise NotImplementedError("Fase 6 del PRD 2026-08-06-motor-de-normativa-territorial.")
