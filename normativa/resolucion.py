"""FASE 1 — El resolver: de un proyecto a la normativa que lo rige.

Implementa el algoritmo de ocho pasos de `docs/design/NORMATIVE_RESOLUTION.md`
§7.3 y el contrato de §8.2. Es puro y sin estado: mismas entradas, mismo
`ConjuntoAplicable`, byte a byte (`TRACEABILITY.md` §10).

Las cuatro decisiones que gobiernan el módulo, todas heredadas del diseño y
ninguna reinventada aquí:

1. **La herencia no es sobrescritura.** El hijo no pisa al padre y "gana la más
   restrictiva" es falso: el CTE no regula la superficie mínima de vivienda, así
   que ahí no hay dos capas que comparar. La composición se resuelve por materia
   × competencia con los cuatro modos de `esquema/competencias.yaml`, que son
   DATOS. Este módulo no sabe nada del reparto competencial español.

2. **Nunca silencio.** Toda regla candidata sale con uno de cuatro estados, y
   todo `no_aplica` sale con motivo escrito. Una regla que desaparece del
   resultado sin decir por qué es indistinguible de una que no existe.

3. **Fail-closed.** Si falta cobertura de una materia exigible al proyecto, no
   se devuelve un conjunto incompleto: se levanta `CoberturaInsuficiente`
   diciendo exactamente qué falta. Devolver la lista de lo que sí tenemos se
   leería como "esto es todo lo que aplica", que es la afirmación insostenible
   que este subsistema existe para impedir.

4. **Los conflictos no se resuelven aquí.** Dos reglas que se contradicen se
   materializan como `Conflicto` con ambas citas y decide el arquitecto
   (`DECISION_ENGINE.md` §3). Un motor que zanja en silencio produce una
   respuesta segura de sí misma y equivocada la mitad de las veces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from . import catalogos, condiciones as cond, loader, manifiesto as _manif
from .ambito import CadenaAmbitos
from .condiciones import Ternario
from .errores import CoberturaInsuficiente
from .modelo import PRIORIDADES, TIPOS_REGLA, Vigencia

ESTADOS = ("aplica", "no_aplica", "aplica_no_evaluable", "sin_cobertura")

# Orden de presentación. Es el orden en que un arquitecto lee la normativa de
# un proyecto: primero el marco estatal, luego el autonómico, luego el
# planeamiento municipal, y al final las afecciones sectoriales, que se
# superponen a todo lo demás y por eso van aparte (§3.3).
ORDEN_NIVEL = {"estatal": 0, "autonomico": 1, "municipal": 2, "sectorial": 3}

# Dentro de un nivel, primero lo que bloquea. NO es jerarquía normativa: son
# ejes independientes y confundirlos se paga en la segunda comunidad autónoma
# (`NORMATIVE_RESOLUTION.md` §7.4).
ORDEN_PRIORIDAD = {p: i for i, p in enumerate(PRIORIDADES)}


# --- Resultado --------------------------------------------------------------

@dataclass(frozen=True)
class FuenteOficial:
    """La cita verificable. Sin esto una regla no es normativa, es una opinión."""

    rango: str
    organismo: str
    identificador_oficial: str
    titulo: str
    boletin: str
    articulo: str
    url_oficial: Optional[str] = None
    norma_concept_id: str = ""
    norma_version: str = ""

    def __str__(self) -> str:
        art = f", {self.articulo}" if self.articulo and self.articulo != "(sin localizar)" else ""
        return f"{self.rango} {self.identificador_oficial}{art} ({self.boletin})"


@dataclass(frozen=True)
class Relacion:
    """Arista tipada hacia otra regla, ya interpretada por el resolver."""

    tipo: str
    destino: str
    nota: str = ""


@dataclass(frozen=True)
class NormaAplicable:
    """Una regla del corpus con su estado resuelto para ESTE proyecto.

    `motivo` es obligatorio en los cuatro estados, no solo en `no_aplica`.
    Saber por qué algo aplica importa tanto como saber por qué no: es lo que
    permite discutir la resolución con el técnico municipal en vez de aceptarla.
    """

    id: str
    nombre: str
    materia: str
    ambito: str
    ambito_nombre: str
    nivel: str
    organismo: str
    version: str
    fecha: str
    fecha_hasta: Optional[str]
    prioridad: str
    motivo: str
    cobertura: str
    fuente: FuenteOficial
    estado: str
    tipo: str
    evaluable: bool
    nivel_de_conocimiento: int
    patron: Optional[str] = None
    valor_parametro: Optional[Any] = None
    unidad: Optional[str] = None
    preguntas_pendientes: Tuple[str, ...] = ()
    relaciones: Tuple[Relacion, ...] = ()
    avisos: Tuple[str, ...] = ()
    traza: Tuple[str, ...] = ()

    @property
    def clave_de_orden(self) -> tuple:
        return (
            ORDEN_NIVEL.get(self.nivel, 9),
            ORDEN_PRIORIDAD.get(self.prioridad, 9),
            self.materia,
            self.id,
        )

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "ambito": {"id": self.ambito, "nombre": self.ambito_nombre, "nivel": self.nivel},
            "organismo": self.organismo,
            "version": self.version,
            "fecha": self.fecha,
            "fecha_hasta": self.fecha_hasta,
            "prioridad": self.prioridad,
            "motivo": self.motivo,
            "cobertura": self.cobertura,
            "fuente_oficial": {
                "rango": self.fuente.rango,
                "identificador_oficial": self.fuente.identificador_oficial,
                "titulo": self.fuente.titulo,
                "boletin": self.fuente.boletin,
                "articulo": self.fuente.articulo,
                "url_oficial": self.fuente.url_oficial,
                "cita": str(self.fuente),
            },
            "estado": self.estado,
            "materia": self.materia,
            "evaluable": self.evaluable,
            "nivel_de_conocimiento": self.nivel_de_conocimiento,
            "valor_parametro": self.valor_parametro,
            "unidad": self.unidad,
            "preguntas_pendientes": list(self.preguntas_pendientes),
            "relaciones": [{"tipo": r.tipo, "destino": r.destino, "nota": r.nota} for r in self.relaciones],
            "avisos": list(self.avisos),
            "traza": list(self.traza),
        }


@dataclass(frozen=True)
class Conflicto:
    """Contradicción real que el motor NO resuelve, por diseño (§7.3 paso 8).

    Existen discrepancias legítimas entre decreto autonómico y ordenanza
    municipal. Zanjarlas por orden de carga o por magnitud del número sería un
    criterio oculto disfrazado de determinismo.
    """

    materia: str
    ambito: str
    reglas: Tuple[str, ...]
    citas: Tuple[str, ...]
    descripcion: str

    def a_dict(self) -> dict:
        return {
            "materia": self.materia,
            "ambito": self.ambito,
            "reglas": list(self.reglas),
            "citas": list(self.citas),
            "descripcion": self.descripcion,
        }


@dataclass(frozen=True)
class MateriaFaltante:
    """Una materia exigible al proyecto sobre la que no se puede afirmar nada."""

    materia: str
    nombre: str
    ambito_esperado: str
    nivel_competente: str
    estado_cobertura: str
    justificacion: str

    def __str__(self) -> str:
        return (
            f"{self.nombre} [{self.materia}] — competencia {self.nivel_competente}, "
            f"ámbito {self.ambito_esperado}, cobertura «{self.estado_cobertura}». "
            f"{self.justificacion}"
        )

    def a_dict(self) -> dict:
        return {
            "materia": self.materia,
            "nombre": self.nombre,
            "ambito_esperado": self.ambito_esperado,
            "nivel_competente": self.nivel_competente,
            "estado_cobertura": self.estado_cobertura,
            "justificacion": self.justificacion,
        }


@dataclass(frozen=True)
class ConjuntoAplicable:
    """La respuesta completa: qué rige, qué no, qué no se puede saber y qué falta.

    Un `ConjuntoAplicable` sin informe de cobertura no se puede interpretar: 12
    reglas cumplidas no significan nada si no se sabe sobre cuántas materias
    (`NORMATIVE_RESOLUTION.md` §8.2).
    """

    normas: Tuple[NormaAplicable, ...]
    conflictos: Tuple[Conflicto, ...]
    cobertura: _manif.InformeCobertura
    faltantes: Tuple[MateriaFaltante, ...]
    preguntas_pendientes: Tuple[str, ...]
    cadena: CadenaAmbitos
    fecha_devengo: date
    asunciones: Tuple[str, ...] = ()
    avisos_de_corpus: Tuple[str, ...] = ()

    @property
    def completo(self) -> bool:
        """False si falta alguna materia exigible. En modo estricto este
        conjunto no llega a construirse: se levanta la excepción."""
        return not self.faltantes

    def aplicables(self) -> Tuple[NormaAplicable, ...]:
        return tuple(n for n in self.normas if n.estado == "aplica")

    def por_estado(self, estado: str) -> Tuple[NormaAplicable, ...]:
        return tuple(n for n in self.normas if n.estado == estado)

    def a_dict(self) -> dict:
        return {
            "normas": [n.a_dict() for n in self.normas],
            "conflictos": [c.a_dict() for c in self.conflictos],
            "cobertura": self.cobertura.a_dict(),
            "faltantes": [f.a_dict() for f in self.faltantes],
            "preguntas_pendientes": list(self.preguntas_pendientes),
            "cadena": [{"id": a.id, "nivel": a.nivel, "nombre": a.nombre} for a in self.cadena.ambitos],
            "fecha_devengo": self.fecha_devengo.isoformat(),
            "completo": self.completo,
            "asunciones": list(self.asunciones),
            "avisos_de_corpus": list(self.avisos_de_corpus),
        }


# --- Estado interno de una candidata ----------------------------------------

@dataclass
class _Candidata:
    """Mutable a propósito, y solo dentro de este módulo.

    Los ocho pasos van estrechando el estado de cada regla; hacerlo con
    dataclasses inmutables obligaría a reconstruir el objeto entero ocho veces
    y no compraría nada, porque nada sale de aquí sin congelarse antes en
    `NormaAplicable`.
    """

    regla: dict
    norma: dict
    ambito_id: str
    estado: str = "aplica"
    motivo: str = ""
    traza: List[str] = field(default_factory=list)
    preguntas: List[str] = field(default_factory=list)
    relaciones: List[Relacion] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    valor_parametro: Optional[Any] = None
    unidad: Optional[str] = None

    @property
    def id(self) -> str:
        return self.regla.get("concept_id", "")

    @property
    def materia(self) -> str:
        return self.regla.get("materia", "")

    @property
    def nivel_territorial(self) -> str:
        return catalogos.nivel_de_ambito(self.ambito_id)

    @property
    def es_sectorial(self) -> bool:
        return bool((self.regla.get("aplicabilidad") or {}).get("sectoriales"))

    @property
    def nivel(self) -> str:
        """Nivel de PRESENTACIÓN. Una regla que exige un sectorial se presenta
        en el bloque sectorial aunque su ámbito territorial sea municipal: es
        el orden en que la lee un arquitecto (§3.3, los sectoriales atraviesan
        la cadena en vez de colgar de ella)."""
        return "sectorial" if self.es_sectorial else self.nivel_territorial

    def descartar(self, motivo: str) -> None:
        """`no_aplica` SIEMPRE con motivo. No hay forma de descartar sin decir
        por qué, y eso es deliberado."""
        self.estado = "no_aplica"
        self.motivo = motivo
        self.traza.append(f"no_aplica: {motivo}")

    def dejar_no_evaluable(self, motivo: str, preguntas: Sequence[str] = ()) -> None:
        # No degrada un `no_aplica` ya decidido: una regla excluida por perfil
        # no vuelve a la vida porque falte un dato de contexto.
        if self.estado == "no_aplica":
            return
        self.estado = "aplica_no_evaluable"
        self.motivo = motivo
        self.preguntas.extend(preguntas)
        self.traza.append(f"aplica_no_evaluable: {motivo}")


# --- Motor ------------------------------------------------------------------

def resolver(
    cadena: CadenaAmbitos,
    perfil,
    fecha_devengo: date,
    ejes_contexto: Optional[Mapping[str, Any]] = None,
    hechos: Optional[Mapping[str, Any]] = None,
    fecha_de_registro: Optional[date] = None,
    raiz_corpus: Optional[Path] = None,
    ruta_manifiesto: Optional[Path] = None,
    estricto: bool = True,
    asunciones: Sequence[str] = (),
) -> ConjuntoAplicable:
    """Los ocho pasos de `NORMATIVE_RESOLUTION.md` §7.3, en orden.

    `hechos` son los datos del proyecto que las condiciones pueden consultar
    (plantas, altura, ocupación...). Lo que no esté ahí no descarta ninguna
    regla: la deja `aplica_no_evaluable` con la pregunta escrita.

    `fecha_de_registro` es el segundo eje bitemporal: reconstruye el informe
    con el corpus que ArchMuse conocía ese día, no con el de hoy. Es lo que
    convierte un informe en defendible tres años después.
    """
    ejes = dict(ejes_contexto or {})
    datos = dict(hechos or {})
    avisos_corpus: List[str] = []

    carga = loader.cargar_cadena(cadena, raiz=raiz_corpus)
    for ruta, fallos in sorted(carga.rechazados.items()):
        avisos_corpus.append(
            f"corpus no cargado ({Path(ruta).name}): {len(fallos)} fallo(s) de validación — "
            f"su materia queda sin cobertura. Primero: {fallos[0]}"
        )

    ids_en_cadena = set(cadena.ids_con_corpus)
    candidatas = _paso1_candidatas(carga, ids_en_cadena, avisos_corpus)
    indice = {c.id: c for c in candidatas}

    _paso2_temporal(candidatas, fecha_devengo, fecha_de_registro)
    _paso3_perfil(candidatas, perfil)
    _paso4_condiciones(candidatas, cadena, datos, ejes)
    grupos = _paso5_agrupacion(candidatas)
    _paso6_composicion(grupos)
    _paso7_aristas(candidatas, indice)
    conflictos = _paso8_conflictos(grupos, indice)
    _marcar_no_evaluables(candidatas)

    rotas = {materia for _, materia in carga.materias_sin_cobertura_por_fallo()}
    informe = _manif.cobertura(cadena, rotas=rotas, ruta=ruta_manifiesto)
    faltantes, preguntas_cobertura = _cobertura_exigible(cadena, perfil, informe)

    normas = tuple(
        sorted(
            (_congelar(c, cadena, informe) for c in candidatas),
            key=lambda n: n.clave_de_orden,
        )
    )

    preguntas = sorted(
        set(preguntas_cobertura) | {p for c in candidatas for p in c.preguntas}
    )

    conjunto = ConjuntoAplicable(
        normas=normas,
        conflictos=conflictos,
        cobertura=informe,
        faltantes=tuple(faltantes),
        preguntas_pendientes=tuple(preguntas),
        cadena=cadena,
        fecha_devengo=fecha_devengo,
        asunciones=tuple(asunciones),
        avisos_de_corpus=tuple(avisos_corpus),
    )

    if estricto and faltantes:
        raise CoberturaInsuficiente(
            cadena=str(cadena),
            faltantes=[str(f) for f in faltantes],
            preguntas=list(preguntas),
        )
    return conjunto


# --- Paso 1: candidatas -----------------------------------------------------

def _paso1_candidatas(
    carga: loader.ResultadoCarga, ids_en_cadena: Set[str], avisos: List[str]
) -> List[_Candidata]:
    """Unión de las reglas de todos los ámbitos de la cadena.

    El ámbito autoritativo es el que declara la regla (`aplicabilidad.ambito`),
    no el directorio donde vive: es el que las validaciones 9 y 11 comprueban.
    Si discrepan, se avisa — un fichero colocado en el directorio equivocado
    aplicaría reglas de un municipio a otro sin que nadie lo notara.
    """
    candidatas: List[_Candidata] = []
    for fichero in carga.ficheros:
        norma = fichero.doc.get("norma") or {}
        for regla in fichero.doc.get("reglas") or []:
            declarado = (regla.get("aplicabilidad") or {}).get("ambito") or fichero.ambito
            if declarado != fichero.ambito:
                avisos.append(
                    f"{regla.get('concept_id')}: declara ámbito «{declarado}» pero el fichero "
                    f"está en el directorio de «{fichero.ambito}». Manda el declarado."
                )
            c = _Candidata(regla=regla, norma=norma, ambito_id=declarado)
            c.traza.append(f"candidata por ámbito {declarado} de la cadena del proyecto")
            if declarado not in ids_en_cadena:
                c.descartar(
                    f"el ámbito declarado «{declarado}» no está en la cadena territorial "
                    f"del proyecto ({', '.join(sorted(ids_en_cadena))})"
                )
            candidatas.append(c)
    return candidatas


# --- Paso 2: filtro temporal ------------------------------------------------

def _vigencia(d: dict) -> Vigencia:
    v = d.get("vigencia") or {}
    def _f(k):
        val = v.get(k)
        return date.fromisoformat(str(val)) if val else None
    return Vigencia(
        vigencia_desde=_f("vigencia_desde") or date.min,
        vigencia_hasta=_f("vigencia_hasta"),
        registro_desde=_f("registro_desde"),
        registro_hasta=_f("registro_hasta"),
    )


def _paso2_temporal(
    candidatas: List[_Candidata], fecha_devengo: date, fecha_de_registro: Optional[date]
) -> None:
    """Vigencia legal a fecha de devengo, y opcionalmente vigencia de registro.

    Una regla fuera de vigencia no se borra del resultado: pasa a `no_aplica`
    con la fecha escrita. Que una norma esté derogada es información, y muchas
    veces es LA información — sobre todo en un proyecto con licencia antigua.
    """
    for c in candidatas:
        if c.estado == "no_aplica":
            continue
        vr, vn = _vigencia(c.regla), _vigencia(c.norma)

        if not vn.vigente_en(fecha_devengo):
            c.descartar(
                f"la norma que la soporta no estaba en vigor el {fecha_devengo.isoformat()} "
                f"(vigencia {vn.vigencia_desde.isoformat()} — "
                f"{vn.vigencia_hasta.isoformat() if vn.vigencia_hasta else 'sin derogar'})"
            )
            continue
        if not vr.vigente_en(fecha_devengo):
            c.descartar(
                f"la regla no estaba en vigor el {fecha_devengo.isoformat()} "
                f"(vigencia {vr.vigencia_desde.isoformat()} — "
                f"{vr.vigencia_hasta.isoformat() if vr.vigencia_hasta else 'sin derogar'})"
            )
            continue

        if fecha_de_registro is not None and not vr.conocida_en(fecha_de_registro):
            c.descartar(
                f"ArchMuse no tenía esta regla en su corpus el "
                f"{fecha_de_registro.isoformat()}: no pudo entrar en un informe de esa fecha"
            )
            continue

        c.traza.append(f"vigente el {fecha_devengo.isoformat()}")


# --- Paso 3: filtro de perfil -----------------------------------------------

def _paso3_perfil(candidatas: List[_Candidata], perfil) -> None:
    """Tipo de intervención, uso y tipología. Lista vacía significa TODOS.

    Es lo que evita que cada regla enumere las 5 tipologías y los 7 tipos de
    intervención — la explosión combinatoria que este diseño existe para
    impedir.
    """
    for c in candidatas:
        if c.estado == "no_aplica":
            continue
        ap = c.regla.get("aplicabilidad") or {}

        tipos = ap.get("tipos_de_intervencion") or []
        if tipos and perfil.tipo_de_intervencion not in tipos:
            c.descartar(
                f"aplica a intervenciones {tipos} y el proyecto es "
                f"«{perfil.tipo_de_intervencion}»"
            )
            continue

        usos = ap.get("usos") or []
        if usos and not any(perfil.cubre_uso(u) for u in usos):
            c.descartar(
                f"aplica a los usos {usos} y el proyecto declara "
                f"{list(perfil.usos_presentes)}"
            )
            continue

        tipologias = ap.get("tipologias") or []
        if tipologias and perfil.tipologia not in tipologias:
            c.descartar(
                f"aplica a las tipologías {tipologias} y el proyecto es «{perfil.tipologia}»"
            )
            continue

        c.traza.append(
            f"perfil compatible (intervención {perfil.tipo_de_intervencion}, "
            f"uso {perfil.uso_principal}, tipología {perfil.tipologia})"
        )


# --- Paso 4: condiciones, sectoriales y parámetros --------------------------

def _paso4_condiciones(
    candidatas: List[_Candidata],
    cadena: CadenaAmbitos,
    hechos: Mapping[str, Any],
    ejes: Mapping[str, Any],
) -> None:
    """Sectoriales declarados + árbol de condiciones + tabla de parámetros.

    Los tres pueden acabar en `aplica_no_evaluable`, y por el mismo motivo: no
    se sabe. Lo que NO puede pasar es que un dato ausente haga desaparecer la
    regla.
    """
    declarados = {s.id: s.declarado for s in cadena.sectoriales}

    for c in candidatas:
        if c.estado == "no_aplica":
            continue

        # --- Sectoriales exigidos por la regla
        exigidos = (c.regla.get("aplicabilidad") or {}).get("sectoriales") or []
        sin_declarar = [s for s in exigidos if declarados.get(s) is None]
        negados = [s for s in exigidos if declarados.get(s) is False]
        if negados:
            c.descartar(
                f"exige el ámbito sectorial {negados} y el proyecto ha declarado "
                f"expresamente que no le afecta"
            )
            continue
        if sin_declarar:
            c.dejar_no_evaluable(
                f"exige el ámbito sectorial {sin_declarar}, sin declarar en el proyecto. "
                f"No declarado no es lo mismo que no aplica",
                [f"¿El proyecto está afectado por {s}?" for s in sin_declarar],
            )
        elif exigidos:
            c.traza.append(f"sectoriales exigidos y declarados presentes: {exigidos}")

        # --- Árbol de condiciones
        r = cond.evaluar(c.regla.get("condiciones"), hechos)
        c.traza.extend(r.traza)
        if r.valor is Ternario.NO:
            c.descartar("sus condiciones de aplicación no se cumplen en este proyecto")
            continue
        if r.valor is Ternario.DESCONOCIDO:
            c.dejar_no_evaluable(
                "no se puede decidir si sus condiciones se cumplen: faltan datos del proyecto",
                [f"Falta el dato «{h}» para decidir si {c.id} aplica" for h in r.hechos_desconocidos],
            )

        # --- Tabla de parámetros
        _resolver_parametro(c, ejes)


def _resolver_parametro(c: _Candidata, ejes: Mapping[str, Any]) -> None:
    """Resuelve el umbral por la cadena de repliegue declarada, y ESCRIBE cuál
    usó (`CONSTRAINT_MODEL.md` §9).

    Un repliegue silencioso en materia autonómica es el Bug #1 de
    `TECH_REVIEW.md` reencarnado en la capa normativa. Si la cadena se agota
    sin valor, la regla queda no evaluable: jamás coge un valor por defecto.
    """
    p = c.regla.get("parametro")
    if not p:
        return
    from .modelo import Parametro

    param = Parametro(
        ejes=tuple(p.get("ejes") or ()),
        valores=tuple(p.get("valores") or ()),
        repliegue=tuple(p.get("repliegue") or ()),
        unidad=p.get("unidad"),
    )
    valor, traza = param.resolver(dict(ejes))
    c.traza.extend(f"parámetro: {t}" for t in traza)
    c.unidad = param.unidad
    if valor is None:
        c.dejar_no_evaluable(
            "no hay valor de parámetro para el contexto de este proyecto y la cadena "
            "de repliegue se agotó sin coger un valor por defecto",
            [f"Falta el umbral de {c.id} para los ejes {list(param.ejes)}"],
        )
    else:
        c.valor_parametro = valor


# --- Paso 5: agrupación por materia -----------------------------------------

def _paso5_agrupacion(candidatas: List[_Candidata]) -> Dict[str, List[_Candidata]]:
    grupos: Dict[str, List[_Candidata]] = {}
    for c in candidatas:
        grupos.setdefault(c.materia, []).append(c)
    return grupos


# --- Paso 6: composición por competencia ------------------------------------

def _paso6_composicion(grupos: Dict[str, List[_Candidata]]) -> None:
    """Los cuatro modos de `esquema/competencias.yaml`, leídos como datos.

    Este es el paso donde el modelo ingenuo (el hijo pisa al padre, o gana la
    más restrictiva) da respuestas legalmente incorrectas con regularidad.
    """
    comps = catalogos.competencias()

    for materia, miembros in grupos.items():
        comp = comps.get(materia)
        vivos = [c for c in miembros if c.estado != "no_aplica"]
        if not comp or not vivos:
            continue
        modo = comp.get("modo")

        if modo == "exclusivo":
            competente = comp.get("competencia")
            for c in vivos:
                if c.nivel_territorial != competente:
                    c.descartar(
                        f"«{materia}» es competencia {competente} exclusiva y esta regla se "
                        f"declara en nivel {c.nivel_territorial}: ese nivel no regula esta "
                        f"materia (no es una cita mal escrita)"
                    )
                else:
                    c.traza.append(f"composición exclusivo: nivel {competente} competente")

        elif modo == "suelo":
            _componer_suelo(materia, comp, vivos)

        elif modo == "acumula":
            for c in vivos:
                c.traza.append(
                    f"composición acumula: «{materia}» se superpone, ninguna capa desplaza a otra"
                )

    _componer_exime(grupos)


def _componer_suelo(materia: str, comp: dict, vivos: List[_Candidata]) -> None:
    """La capa competente fija el mínimo; las autorizadas pueden endurecerlo.

    **Aquí no se sustituye nada.** El diseño (§7.3) prevé que la regla inferior
    sustituya a la base cuando endurece, pero decidir si endurece exige conocer
    la DIRECCIÓN de la comparación ("mínimo de" vs "máximo de"), y el esquema
    del corpus no tiene hoy ningún campo que la declare. Deducirla de la
    magnitud del número sería exactamente el "gana la más restrictiva" que
    §7.1 declara incorrecto. Así que ambas se conservan y se anota la relación
    cuando la propia regla la declara con una arista `endurece`.

    Es una limitación consciente y está documentada como tal: conservar las dos
    normas nunca produce una respuesta falsa, solo una lista más larga.
    """
    competente = comp.get("competencia")
    permitidos = comp.get("permite_endurecer") or []
    base = [c for c in vivos if c.nivel_territorial == competente]

    for c in vivos:
        if c.nivel_territorial == competente:
            c.traza.append(f"composición suelo: base {competente} de «{materia}»")
            continue
        if c.nivel_territorial not in permitidos:
            c.descartar(
                f"«{materia}» tiene suelo {competente} y el nivel {c.nivel_territorial} "
                f"no está autorizado a endurecerla"
            )
            continue
        declaradas = [
            a for a in (c.regla.get("aristas") or []) if a.get("tipo") == "endurece"
        ]
        if declaradas:
            for a in declaradas:
                c.relaciones.append(
                    Relacion("endurece", a["destino"], "endurece el suelo estatal declarado")
                )
            c.traza.append(
                f"composición suelo: endurece {[a['destino'] for a in declaradas]}"
            )
        elif base:
            c.avisos.append(
                f"regla de nivel {c.nivel_territorial} en materia de suelo {competente} que "
                f"no declara con una arista «endurece» a qué regla base afecta: se aplican "
                f"ambas, y el corpus debería declararlo"
            )


def _componer_exime(grupos: Dict[str, List[_Candidata]]) -> None:
    """Modo `exime`: una regla retira la aplicabilidad de otra, bajo condición.

    Solo exime la que efectivamente aplica. Si la eximente quedó
    `aplica_no_evaluable` —porque no se sabe si su condición se cumple— la
    eximida NO se descarta: queda también no evaluable con la pregunta. Eximir
    con una condición sin comprobar es la forma más silenciosa de perder una
    exigencia.
    """
    comps = catalogos.competencias()
    todas = {c.id: c for grupo in grupos.values() for c in grupo}

    for c in todas.values():
        comp = comps.get(c.materia) or {}
        if not comp.get("puede_eximir"):
            continue
        for a in c.regla.get("aristas") or []:
            if a.get("tipo") != "exime_de":
                continue
            objetivo = todas.get(a["destino"])
            if objetivo is None or objetivo.estado == "no_aplica":
                continue
            cita = _cita_corta(c)
            if c.estado == "aplica":
                objetivo.descartar(f"eximida por {c.id} ({cita})")
                objetivo.relaciones.append(Relacion("eximida_por", c.id, cita))
            elif c.estado == "aplica_no_evaluable":
                objetivo.dejar_no_evaluable(
                    f"podría estar eximida por {c.id} ({cita}), pero no se puede comprobar "
                    f"si la exención se cumple",
                    list(c.preguntas),
                )
                objetivo.relaciones.append(Relacion("posible_exencion", c.id, cita))


# --- Paso 7: aristas --------------------------------------------------------

def _paso7_aristas(candidatas: List[_Candidata], indice: Dict[str, _Candidata]) -> None:
    """`remite_a`, `se_mide_segun`, `corrige_erratum`, `desarrolla`.

    `deroga` y `modifica` ya quedaron resueltas en el paso 2 vía vigencia.
    `exime_de` se resolvió en el paso 6, donde están las competencias.

    Una remisión NO arrastra a la regla de destino al conjunto aplicable: si el
    destino no encaja en el perfil del proyecto, forzarlo sería inventar
    aplicabilidad. Se anota la relación, y si el destino no está en el corpus
    cargado se avisa — una remisión rota es una laguna, no un detalle.
    """
    seguibles = ("remite_a", "se_mide_segun", "corrige_erratum", "desarrolla")
    for c in candidatas:
        if c.estado == "no_aplica":
            continue
        for a in c.regla.get("aristas") or []:
            tipo, destino = a.get("tipo"), a.get("destino")
            if tipo not in seguibles:
                continue
            objetivo = indice.get(destino)
            if objetivo is None:
                nota = "destino fuera del corpus cargado para esta cadena"
                c.avisos.append(
                    f"arista «{tipo}» hacia «{destino}»: no está en el corpus de esta cadena "
                    f"territorial, así que la remisión no se puede seguir"
                )
            elif objetivo.estado == "no_aplica":
                nota = f"el destino no aplica a este proyecto: {objetivo.motivo}"
                c.avisos.append(
                    f"arista «{tipo}» hacia «{destino}», que no aplica a este proyecto: "
                    f"revisar si la remisión deja la exigencia sin contenido"
                )
            else:
                nota = f"destino en estado «{objetivo.estado}»"
            c.relaciones.append(Relacion(tipo, destino, nota))
            c.traza.append(f"arista {tipo} -> {destino} ({nota})")


# --- Paso 8: conflictos -----------------------------------------------------

def _paso8_conflictos(
    grupos: Dict[str, List[_Candidata]], indice: Dict[str, _Candidata]
) -> Tuple[Conflicto, ...]:
    """Lo que sigue en contradicción NO se resuelve: se expone con ambas citas.

    Detecta el hueco que la validación 14 no puede cubrir. Aquella prohíbe en
    carga dos reglas con clave de perfil IDÉNTICA; aquí aparecen las que se
    SOLAPAN sin ser idénticas — una con `usos: []` (todos) y otra con
    `usos: [residencial]` conviven en el corpus y ambas caen sobre el mismo
    proyecto residencial. Sin este paso, el resolver tendría que desempatar en
    silencio, que es el riesgo que `CONFLICT_ENGINE.md` §2 nombra como el más
    probable bajo presión de entrega.
    """
    relacionadas = {
        (c.id, r.destino) for c in indice.values() for r in c.relaciones
    }
    conflictos: List[Conflicto] = []

    for materia, miembros in sorted(grupos.items()):
        activos = [c for c in miembros if c.estado == "aplica"]
        por_clave: Dict[tuple, List[_Candidata]] = {}
        for c in activos:
            por_clave.setdefault((c.ambito_id, c.regla.get("patron")), []).append(c)

        for (ambito, patron), competidoras in sorted(por_clave.items(), key=lambda kv: str(kv[0])):
            if len(competidoras) < 2 or not patron:
                continue
            ids = sorted(c.id for c in competidoras)
            # Si el corpus declara una relación entre ellas, no hay
            # contradicción: hay una jerarquía escrita, que es justo lo que se
            # le pide al Curador.
            if any(
                (a, b) in relacionadas or (b, a) in relacionadas
                for i, a in enumerate(ids)
                for b in ids[i + 1:]
            ):
                continue
            conflictos.append(
                Conflicto(
                    materia=materia,
                    ambito=ambito,
                    reglas=tuple(ids),
                    citas=tuple(_cita_corta(c) for c in sorted(competidoras, key=lambda x: x.id)),
                    descripcion=(
                        f"{len(ids)} reglas de «{materia}» aplican simultáneamente en el ámbito "
                        f"{ambito} con el mismo patrón «{patron}» y ninguna declara relación con "
                        f"la otra. El motor no desempata: decide el arquitecto."
                    ),
                )
            )
            for c in competidoras:
                c.avisos.append(
                    f"en conflicto no resuelto con {[i for i in ids if i != c.id]}"
                )

    return tuple(conflictos)


# --- Cierre: lo que rige pero no se puntúa ----------------------------------

_ETIQUETA_TIPO = {
    "exigencia_cualitativa": "es cualitativa y requiere juicio humano",
    "definicion": "define un término que usan otras reglas",
    "remision": "no dice nada propio: remite a otra norma",
    "procedimental": "es de trámite o régimen transitorio",
}


def _marcar_no_evaluables(candidatas: List[_Candidata]) -> None:
    """Cuatro de los siete tipos de regla NO son evaluables por un motor
    geométrico, y eso es correcto: un corpus honesto contiene mucha norma que
    solo se puede comprobar leyéndola (`NORMATIVE_ENGINE.md` §6).

    Esas reglas RIGEN el proyecto —van en la lista, con su cita— pero salen
    como `aplica_no_evaluable`, que es el estado que §8.2 reserva justamente
    para esto. Dejarlas en `aplica` sería prometer una comprobación que nunca
    se hace; descartarlas sería peor, porque son las que más veces acaban en un
    reparo de licencia.

    Se hace al final, después de la composición, para que un `no_aplica` bien
    razonado no se convierta en "no evaluable" por el camino.
    """
    for c in candidatas:
        if c.estado != "aplica" or TIPOS_REGLA.get(c.regla.get("tipo"), False):
            continue
        motivo_previo = c.motivo
        c.estado = "aplica_no_evaluable"
        c.motivo = (
            f"rige el proyecto, pero {_ETIQUETA_TIPO.get(c.regla.get('tipo'), 'no es evaluable')}: "
            f"se informa y se cita, no se puntúa"
        )
        c.traza.append(f"aplica_no_evaluable por tipo «{c.regla.get('tipo')}»")
        if motivo_previo:
            c.traza.append(f"motivo de aplicabilidad: {motivo_previo}")


# --- Cobertura exigible: el cierre fail-closed ------------------------------

def _cobertura_exigible(
    cadena: CadenaAmbitos, perfil, informe: _manif.InformeCobertura
) -> Tuple[List[MateriaFaltante], List[str]]:
    """Qué materias son exigibles a ESTE proyecto y sobre cuáles no se puede
    afirmar nada.

    La exigibilidad es ternaria, como las condiciones y por el mismo motivo: un
    sectorial sin declarar no hace la materia "no exigible", la deja en
    pregunta. Una materia exigible sin cobertura bloquea; una materia de
    exigibilidad desconocida pregunta. Confundir las dos convertiría cada
    proyecto sin declarar patrimonio en un informe bloqueado, y la reacción
    natural sería relajar el bloqueo — perdiendo el que sí importa.
    """
    reglas = catalogos.exigibilidad()
    materias = catalogos.materias()
    comps = catalogos.competencias()
    estados = {e.materia: e for e in informe.entradas}
    declarados = {s.id: s.declarado for s in cadena.sectoriales}

    faltantes: List[MateriaFaltante] = []
    preguntas: List[str] = []

    for materia_id in sorted(materias):
        regla = reglas.get(materia_id)
        if not regla:
            # Una materia del catálogo sin declaración de exigibilidad no se
            # asume no exigible: se pregunta. El silencio no es una respuesta.
            preguntas.append(
                f"«{materia_id}» no declara exigibilidad en esquema/exigibilidad.yaml: "
                f"no se puede decidir si este proyecto la necesita"
            )
            continue

        veredicto, motivo = _es_exigible(regla, perfil, declarados)
        if veredicto is Ternario.NO:
            continue
        if veredicto is Ternario.DESCONOCIDO:
            preguntas.append(motivo)
            continue

        entrada = estados.get(materia_id)
        if entrada is not None and entrada.afirmable:
            continue

        comp = comps.get(materia_id) or {}
        faltantes.append(
            MateriaFaltante(
                materia=materia_id,
                nombre=materias[materia_id].get("nombre", materia_id),
                ambito_esperado=entrada.ambito if entrada else cadena.mas_especifico.id,
                nivel_competente=comp.get("competencia", "?"),
                estado_cobertura=entrada.estado if entrada else "ausente",
                justificacion=regla.get("justificacion", "").strip(),
            )
        )

    return faltantes, preguntas


def _es_exigible(regla: dict, perfil, declarados: Mapping[str, Optional[bool]]) -> Tuple[Ternario, str]:
    modo = regla.get("exigible", "siempre")
    materia = regla.get("materia", "?")

    excepto = regla.get("excepto_tipos_de_intervencion") or []
    if perfil.tipo_de_intervencion in excepto:
        return Ternario.NO, ""

    if modo == "nunca":
        return Ternario.NO, ""

    if modo == "siempre":
        return Ternario.SI, ""

    if modo == "si_uso":
        usos = regla.get("usos") or []
        if any(perfil.cubre_uso(u) for u in usos):
            return Ternario.SI, ""
        return Ternario.NO, ""

    if modo == "si_sectorial":
        sectoriales = regla.get("sectoriales") or []
        if any(declarados.get(s) is True for s in sectoriales):
            return Ternario.SI, ""
        sin_declarar = [s for s in sectoriales if declarados.get(s) is None]
        if sin_declarar:
            return Ternario.DESCONOCIDO, (
                f"No se puede saber si «{materia}» es exigible: el proyecto no declara "
                f"si le afectan {sin_declarar}. Sin declararlo, ni se exige ni se descarta."
            )
        return Ternario.NO, ""

    return Ternario.DESCONOCIDO, (
        f"«{materia}» declara un modo de exigibilidad no reconocido («{modo}»)"
    )


# --- Congelado --------------------------------------------------------------

def _cita_corta(c: _Candidata) -> str:
    f = (c.norma.get("fuente") or {})
    return f"{f.get('rango', '?')} {f.get('identificador_oficial', '?')}"


def _articulo_str(norma: dict) -> str:
    from .modelo import Articulo

    a = norma.get("articulo") or {}
    return str(
        Articulo(
            documento_basico=a.get("documento_basico"),
            seccion=a.get("seccion"),
            apartado=a.get("apartado"),
            punto=a.get("punto"),
            tabla=a.get("tabla"),
        )
    )


def _nombre_ambito(cadena: CadenaAmbitos, ambito_id: str) -> str:
    for a in cadena.ambitos:
        if a.id == ambito_id:
            return a.nombre
    return ambito_id


def _congelar(
    c: _Candidata, cadena: CadenaAmbitos, informe: _manif.InformeCobertura
) -> NormaAplicable:
    fuente = c.norma.get("fuente") or {}
    vr = _vigencia(c.regla)
    entrada = next(
        (e for e in informe.entradas if e.materia == c.materia and e.ambito == c.ambito_id),
        None,
    )
    if c.estado == "aplica" and not c.motivo:
        c.motivo = (
            f"rige el proyecto: ámbito {c.ambito_id} de su cadena territorial, perfil "
            f"compatible y vigente en la fecha de devengo"
        )

    return NormaAplicable(
        id=c.id,
        nombre=c.regla.get("nombre", ""),
        materia=c.materia,
        ambito=c.ambito_id,
        ambito_nombre=_nombre_ambito(cadena, c.ambito_id),
        nivel=c.nivel,
        organismo=fuente.get("organismo", ""),
        version=c.regla.get("instance_id", ""),
        fecha=vr.vigencia_desde.isoformat(),
        fecha_hasta=vr.vigencia_hasta.isoformat() if vr.vigencia_hasta else None,
        prioridad=c.regla.get("prioridad", ""),
        motivo=c.motivo,
        cobertura=entrada.estado if entrada else "ausente",
        fuente=FuenteOficial(
            rango=fuente.get("rango", ""),
            organismo=fuente.get("organismo", ""),
            identificador_oficial=fuente.get("identificador_oficial", ""),
            titulo=fuente.get("titulo", ""),
            boletin=fuente.get("boletin", ""),
            articulo=_articulo_str(c.norma),
            url_oficial=fuente.get("url_oficial"),
            norma_concept_id=c.norma.get("concept_id", ""),
            norma_version=c.norma.get("instance_id", ""),
        ),
        estado=c.estado,
        tipo=c.regla.get("tipo", ""),
        evaluable=TIPOS_REGLA.get(c.regla.get("tipo"), False) and c.estado == "aplica",
        nivel_de_conocimiento=c.regla.get("nivel_de_conocimiento", 0),
        patron=c.regla.get("patron"),
        valor_parametro=c.valor_parametro,
        unidad=c.unidad,
        preguntas_pendientes=tuple(sorted(set(c.preguntas))),
        relaciones=tuple(c.relaciones),
        avisos=tuple(c.avisos),
        traza=tuple(c.traza),
    )
