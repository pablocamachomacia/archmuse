"""Modelo de estado del entrevistador arquitectónico — Fase A.

Fase A del plan de implementación (`docs/design/2026-08-12-plan-implementacion-
entrevistador.md`): **solo** estructuras de datos y su serialización a/desde
JSON. Nada de este módulo llama a Flask, a Claude, ni sabe que
`analyzer/ai_generator.py` existe — es la base de la que dependen todas las
fases siguientes (principio de aislamiento del plan).

Fuentes normativas, en orden de autoridad para cada esquema:

- `EstadoEntrevista`, `RespuestaInterpretada`, `CampoEspecificacion`,
  `EspecificacionArquitectonica` → PRD `docs/prd/2026-08-12-entrevistador-
  generador.md` v2, §22 (Especificación) y §24 (Estado de conversación).
- `DirectivaCualitativa`, `ContextoCualitativo`, `TrazaDeGeneracion` →
  contrato `docs/design/2026-08-12-contrato-entrevistador-generador.md`,
  §6.1-§6.3.

Dos decisiones de diseño que no estaban explícitas en ninguno de los dos
documentos y que esta implementación fija aquí (ver informe de cierre de
Fase A para el detalle):

1. **Catálogo cerrado de las 15 categorías de la Especificación**
   (`CATEGORIAS_ESPECIFICACION`), con el mismo criterio de error explícito
   que el contrato ya exigía para las 5 categorías de `DirectivaCualitativa`
   (Decisión Pablo #3). El PRD no lo pedía explícitamente para este catálogo,
   pero el mismo principio de "cerrado por defecto, error si se sale" aplica
   igual de bien aquí y evita categorías inventadas por error tipográfico.
2. **Solo se valida la forma del dato (pertenencia a un catálogo cerrado),
   nunca una regla de negocio "solo si..."** (p. ej. "`confianza` solo si
   `tipo_dato = inferencia`"). Esas reglas cruzadas son responsabilidad del
   motor (Fase C) y del compilador (Fase D), que todavía no existen — este
   módulo no las implementa ni las simula, para no invadir esas fases.

Ningún campo de este módulo tiene un valor por defecto silencioso que
disfrace un dato ausente como si fuera uno real: donde falta información, el
campo queda `None` o en una lista vacía explícita, nunca un valor inventado
(mismo principio que TECH_REVIEW.md § "Bug #1" y que `storage.py` ya aplica
para `modelo`).

Los campos de tipo `Any` (`valor`, `respuesta_cruda`) deben ser tipos
serializables a JSON (str, int, float, bool, list, dict, None) — no se valida
aquí; es responsabilidad de quien los construya (Fase C/D).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# --- Identificadores e infraestructura mínima -------------------------------

_ID_LEN = 12


def nuevo_id() -> str:
    """Mismo esquema que `storage._ID_RE`: hex de 12 caracteres, generado
    aquí, nunca derivado de entrada de usuario — misma razón que en
    storage.py: es la defensa contra ids adivinables o inyectados."""
    return uuid.uuid4().hex[:_ID_LEN]


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validar_enum(valor: Any, permitidos: tuple, campo: str, clase: str) -> None:
    if valor not in permitidos:
        raise ValueError(
            "%s.%s: %r no pertenece al catálogo cerrado %s"
            % (clase, campo, valor, permitidos)
        )


def _validar_enum_opcional(valor: Any, permitidos: tuple, campo: str, clase: str) -> None:
    if valor is not None:
        _validar_enum(valor, permitidos, campo, clase)


def _lista_a_dict(items) -> list:
    return [item.a_dict() for item in items]


# --- Catálogos cerrados -------------------------------------------------

#: Las 15 categorías de la Especificación Arquitectónica (PRD v2 §1). Cerrado
#: por el mismo criterio que el catálogo de directivas: añadir una categoría
#: nueva es una decisión de producto, no un detalle de implementación.
CATEGORIAS_ESPECIFICACION = (
    "contexto_ubicacion",
    "parcela",
    "programa_necesidades",
    "usuarios_forma_vida",
    "prioridades_trade_offs",
    "restricciones_normativas",
    "entorno_privacidad",
    "orientacion_clima",
    "espacios_exteriores",
    "movilidad_accesos",
    "sostenibilidad_eficiencia",
    "identidad_arquitectonica",
    "presupuesto",
    "relaciones_espaciales_circulacion",
    "estructura_sistema_constructivo",
)

#: `RespuestaInterpretada.naturaleza` — taxonomía reutilizada de
#: `docs/brain/FACT_MODEL.md`, sin "Recomendación" (el entrevistador recoge,
#: no recomienda).
NATURALEZAS_RESPUESTA = ("Hecho", "Inferencia", "Hipótesis", "Preferencia")

#: Confianza cualitativa, nunca numérica — mismo principio en todo el
#: proyecto (ver `docs/design/TRACEABILITY.md`).
CONFIANZAS = ("Alta", "Media", "Baja")

#: `CampoEspecificacion.tipo_dato` (PRD v2 §22.2).
TIPOS_DATO_CAMPO = ("información_usuario", "inferencia", "preferencia", "restricción")

#: `CampoEspecificacion.destino_generador` (PRD v2 §22.2).
DESTINOS_GENERADOR = (
    "usado_directo",
    "usado_via_extension_minima",
    "almacenado_sin_uso",
    "no_aplica",
)

#: `CampoEspecificacion.decision_contrato` (PRD v2 §17).
DECISIONES_CONTRATO = ("A", "B", "C")

#: `EspecificacionArquitectonica.modo_origen` (PRD v2 §22.1).
MODOS_ORIGEN_ESPECIFICACION = ("entrevista_guiada", "edicion_experta", "mixto")

#: `EstadoEntrevista.modo` / `.modo_entrada` (PRD v2 §24, §29).
MODOS_ENTREVISTA = ("entrevista_guiada", "edicion_experta")

#: `EstadoEntrevista.estado` — ciclo de vida de la sesión. No estaba
#: nombrado explícitamente en el PRD/contrato; lo introduce esta
#: implementación porque B4/E9 (recuperar tras abandono) lo necesitan.
ESTADOS_CICLO_VIDA = ("en_curso", "cerrada", "abandonada")

#: `DirectivaCualitativa.categoria` — catálogo cerrado por defecto
#: (Decisión Pablo #3). Contrato §6.1.
CATEGORIAS_DIRECTIVA = (
    "no_negociable",
    "privacidad",
    "accesibilidad",
    "caracter",
    "relacion_espacial",
)

#: `DirectivaCualitativa.fuerza` — contrato §6.1.
FUERZAS_DIRECTIVA = ("dura", "blanda")

#: `VerificacionDeterminista.resultado` — contrato §6.3.
RESULTADOS_VERIFICACION = ("cumple", "no_cumple", "no_verificable")


# --- Turno / respuesta cruda ---------------------------------------------


@dataclass
class Turno:
    """Un turno de entrevista: una o varias preguntas presentadas juntas
    (el bloque fijo agrupa 3, PRD v2 §21.3) y la respuesta cruda del
    usuario a cada una. Es el extremo de la cadena de trazabilidad: para
    cualquier `CampoEspecificacion.origen`, el texto literal que lo originó
    vive aquí (criterio de aceptación de D5 del plan)."""

    turno_id: str
    preguntas_ids: list[str] = field(default_factory=list)
    respuesta_cruda: dict[str, Any] = field(default_factory=dict)
    creado_en: str = field(default_factory=_ahora)

    def a_dict(self) -> dict:
        return {
            "turno_id": self.turno_id,
            "preguntas_ids": list(self.preguntas_ids),
            "respuesta_cruda": dict(self.respuesta_cruda),
            "creado_en": self.creado_en,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "Turno":
        return Turno(
            turno_id=datos["turno_id"],
            preguntas_ids=list(datos.get("preguntas_ids") or []),
            respuesta_cruda=dict(datos.get("respuesta_cruda") or {}),
            creado_en=datos.get("creado_en") or _ahora(),
        )


@dataclass
class RespuestaInterpretada:
    """Lo que el motor (Fase C) extrae de un turno: un valor con su
    naturaleza epistémica declarada (PRD v2 §22.3: "respuesta →
    interpretación" es el primer tramo de la cadena de trazabilidad)."""

    respuesta_id: str
    turno_id: str
    especificacion_id: str
    respuesta_cruda: Any
    naturaleza: str
    valor: Any = None
    confianza: Optional[str] = None
    motivo: Optional[str] = None

    def __post_init__(self) -> None:
        _validar_enum(self.naturaleza, NATURALEZAS_RESPUESTA, "naturaleza", "RespuestaInterpretada")
        _validar_enum_opcional(self.confianza, CONFIANZAS, "confianza", "RespuestaInterpretada")

    def a_dict(self) -> dict:
        return {
            "respuesta_id": self.respuesta_id,
            "turno_id": self.turno_id,
            "especificacion_id": self.especificacion_id,
            "respuesta_cruda": self.respuesta_cruda,
            "naturaleza": self.naturaleza,
            "valor": self.valor,
            "confianza": self.confianza,
            "motivo": self.motivo,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "RespuestaInterpretada":
        return RespuestaInterpretada(
            respuesta_id=datos["respuesta_id"],
            turno_id=datos["turno_id"],
            especificacion_id=datos["especificacion_id"],
            respuesta_cruda=datos.get("respuesta_cruda"),
            naturaleza=datos["naturaleza"],
            valor=datos.get("valor"),
            confianza=datos.get("confianza"),
            motivo=datos.get("motivo"),
        )


@dataclass
class ValorEnConflicto:
    """Un valor concreto dentro de una `Contradiccion` — de qué turno vino
    y qué decía, para poder presentar el conflicto sin ocultar ninguno de
    los dos lados (PRD v2 §26: nunca se sobrescribe en silencio)."""

    turno_id: str
    valor: Any

    def a_dict(self) -> dict:
        return {"turno_id": self.turno_id, "valor": self.valor}

    @staticmethod
    def desde_dict(datos: dict) -> "ValorEnConflicto":
        return ValorEnConflicto(turno_id=datos["turno_id"], valor=datos.get("valor"))


@dataclass
class Contradiccion:
    """Dos (o más) respuestas incompatibles sobre el mismo
    `especificacion_id`. `resuelta=False` bloquea el criterio de parada
    (PRD v2 §28) hasta que el usuario decide — el motor (Fase C) es quien
    la detecta y quien la marca resuelta, este módulo solo la representa."""

    contradiccion_id: str
    especificacion_id: str
    valores_en_conflicto: list[ValorEnConflicto] = field(default_factory=list)
    resuelta: bool = False
    valor_resuelto: Any = None
    resuelta_en_turno_id: Optional[str] = None

    def a_dict(self) -> dict:
        return {
            "contradiccion_id": self.contradiccion_id,
            "especificacion_id": self.especificacion_id,
            "valores_en_conflicto": _lista_a_dict(self.valores_en_conflicto),
            "resuelta": self.resuelta,
            "valor_resuelto": self.valor_resuelto,
            "resuelta_en_turno_id": self.resuelta_en_turno_id,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "Contradiccion":
        return Contradiccion(
            contradiccion_id=datos["contradiccion_id"],
            especificacion_id=datos["especificacion_id"],
            valores_en_conflicto=[
                ValorEnConflicto.desde_dict(v) for v in datos.get("valores_en_conflicto") or []
            ],
            resuelta=bool(datos.get("resuelta", False)),
            valor_resuelto=datos.get("valor_resuelto"),
            resuelta_en_turno_id=datos.get("resuelta_en_turno_id"),
        )


@dataclass
class EstadoEntrevista:
    """El estado completo de una sesión de entrevista (PRD v2 §24).

    `estado` (ciclo de vida: en_curso/cerrada/abandonada) es distinto de
    `modo` (entrevista_guiada/edicion_experta, el modo *activo* — puede
    cambiar a mitad de camino, E8 del plan) y de `modo_entrada` (el modo
    con el que se creó la sesión, fijo, PRD v2 §24 lo introduce para saber
    si §29 — modo experto — aplica desde el inicio).

    Los límites de llamadas a IA (5) y de turnos (20, PRD v2 §28) **no se
    enforzan aquí a propósito** — pertenecen al motor de entrevista (Fase
    C), todavía sin implementar. Este dataclass solo guarda los contadores;
    decidir cuándo cerrar la entrevista no es responsabilidad del modelo de
    datos.
    """

    sesion_id: str
    estado: str = "en_curso"
    modo: str = "entrevista_guiada"
    modo_entrada: str = "entrevista_guiada"
    historial_turnos: list[Turno] = field(default_factory=list)
    respuestas_interpretadas: list[RespuestaInterpretada] = field(default_factory=list)
    contradicciones: list[Contradiccion] = field(default_factory=list)
    no_negociables: list[str] = field(default_factory=list)
    llamadas_ia_consumidas: int = 0
    turnos_totales: int = 0
    creado_en: str = field(default_factory=_ahora)
    modificado_en: str = field(default_factory=_ahora)

    def __post_init__(self) -> None:
        _validar_enum(self.estado, ESTADOS_CICLO_VIDA, "estado", "EstadoEntrevista")
        _validar_enum(self.modo, MODOS_ENTREVISTA, "modo", "EstadoEntrevista")
        _validar_enum(self.modo_entrada, MODOS_ENTREVISTA, "modo_entrada", "EstadoEntrevista")
        if self.llamadas_ia_consumidas < 0:
            raise ValueError("EstadoEntrevista.llamadas_ia_consumidas no puede ser negativo")
        if self.turnos_totales < 0:
            raise ValueError("EstadoEntrevista.turnos_totales no puede ser negativo")

    def a_dict(self) -> dict:
        return {
            "sesion_id": self.sesion_id,
            "estado": self.estado,
            "modo": self.modo,
            "modo_entrada": self.modo_entrada,
            "historial_turnos": _lista_a_dict(self.historial_turnos),
            "respuestas_interpretadas": _lista_a_dict(self.respuestas_interpretadas),
            "contradicciones": _lista_a_dict(self.contradicciones),
            "no_negociables": list(self.no_negociables),
            "llamadas_ia_consumidas": self.llamadas_ia_consumidas,
            "turnos_totales": self.turnos_totales,
            "creado_en": self.creado_en,
            "modificado_en": self.modificado_en,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "EstadoEntrevista":
        return EstadoEntrevista(
            sesion_id=datos["sesion_id"],
            estado=datos.get("estado", "en_curso"),
            modo=datos.get("modo", "entrevista_guiada"),
            modo_entrada=datos.get("modo_entrada", "entrevista_guiada"),
            historial_turnos=[Turno.desde_dict(t) for t in datos.get("historial_turnos") or []],
            respuestas_interpretadas=[
                RespuestaInterpretada.desde_dict(r) for r in datos.get("respuestas_interpretadas") or []
            ],
            contradicciones=[Contradiccion.desde_dict(c) for c in datos.get("contradicciones") or []],
            no_negociables=list(datos.get("no_negociables") or []),
            llamadas_ia_consumidas=int(datos.get("llamadas_ia_consumidas", 0)),
            turnos_totales=int(datos.get("turnos_totales", 0)),
            creado_en=datos.get("creado_en") or _ahora(),
            modificado_en=datos.get("modificado_en") or _ahora(),
        )


# --- Especificación Arquitectónica ---------------------------------------


@dataclass
class CampoEspecificacion:
    """La unidad de la Especificación (PRD v2 §22.2). `especificacion_id`
    es un concept_id estable — sobrevive a correcciones (mismo principio
    que `docs/brain/FACT_MODEL.md` §7)."""

    especificacion_id: str
    categoria: str
    etiqueta: str
    tipo_dato: str
    valor: Any = None
    origen: list[str] = field(default_factory=list)
    confianza: Optional[str] = None
    destino_generador: str = "no_aplica"
    decision_contrato: Optional[str] = None
    editable_por_usuario: bool = True

    def __post_init__(self) -> None:
        _validar_enum(self.categoria, CATEGORIAS_ESPECIFICACION, "categoria", "CampoEspecificacion")
        _validar_enum(self.tipo_dato, TIPOS_DATO_CAMPO, "tipo_dato", "CampoEspecificacion")
        _validar_enum_opcional(self.confianza, CONFIANZAS, "confianza", "CampoEspecificacion")
        _validar_enum(self.destino_generador, DESTINOS_GENERADOR, "destino_generador", "CampoEspecificacion")
        _validar_enum_opcional(
            self.decision_contrato, DECISIONES_CONTRATO, "decision_contrato", "CampoEspecificacion"
        )

    def a_dict(self) -> dict:
        return {
            "especificacion_id": self.especificacion_id,
            "categoria": self.categoria,
            "etiqueta": self.etiqueta,
            "tipo_dato": self.tipo_dato,
            "valor": self.valor,
            "origen": list(self.origen),
            "confianza": self.confianza,
            "destino_generador": self.destino_generador,
            "decision_contrato": self.decision_contrato,
            "editable_por_usuario": self.editable_por_usuario,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "CampoEspecificacion":
        return CampoEspecificacion(
            especificacion_id=datos["especificacion_id"],
            categoria=datos["categoria"],
            etiqueta=datos["etiqueta"],
            tipo_dato=datos["tipo_dato"],
            valor=datos.get("valor"),
            origen=list(datos.get("origen") or []),
            confianza=datos.get("confianza"),
            destino_generador=datos.get("destino_generador", "no_aplica"),
            decision_contrato=datos.get("decision_contrato"),
            editable_por_usuario=bool(datos.get("editable_por_usuario", True)),
        )


@dataclass
class DirectivaCualitativa:
    """Contrato §6.1. `categoria` es el catálogo cerrado por defecto
    (Decisión Pablo #3): construir una con una categoría fuera de
    `CATEGORIAS_DIRECTIVA` lanza `ValueError` explícito — ampliarlo exige
    tocar esta lista a mano, nunca un valor libre que llegue por dato."""

    especificacion_id: str
    categoria: str
    fuerza: str
    texto_origen: str
    texto_prompt: str
    verificable_geometricamente: bool = False

    def __post_init__(self) -> None:
        _validar_enum(self.categoria, CATEGORIAS_DIRECTIVA, "categoria", "DirectivaCualitativa")
        _validar_enum(self.fuerza, FUERZAS_DIRECTIVA, "fuerza", "DirectivaCualitativa")

    def a_dict(self) -> dict:
        return {
            "especificacion_id": self.especificacion_id,
            "categoria": self.categoria,
            "fuerza": self.fuerza,
            "texto_origen": self.texto_origen,
            "texto_prompt": self.texto_prompt,
            "verificable_geometricamente": self.verificable_geometricamente,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "DirectivaCualitativa":
        return DirectivaCualitativa(
            especificacion_id=datos["especificacion_id"],
            categoria=datos["categoria"],
            fuerza=datos["fuerza"],
            texto_origen=datos["texto_origen"],
            texto_prompt=datos["texto_prompt"],
            verificable_geometricamente=bool(datos.get("verificable_geometricamente", False)),
        )


@dataclass
class ContextoCualitativo:
    """Contrato §6.2 — lo que de verdad recibiría `ai_generator.py` en la
    Fase F (todavía no implementada). `directivas` se conserva para la
    trazabilidad server-side; `texto_prompt` es la compilación determinista
    ya agrupada por `fuerza` que se anexaría al mensaje."""

    directivas: list[DirectivaCualitativa] = field(default_factory=list)
    texto_prompt: str = ""

    def a_dict(self) -> dict:
        return {
            "directivas": _lista_a_dict(self.directivas),
            "texto_prompt": self.texto_prompt,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "ContextoCualitativo":
        return ContextoCualitativo(
            directivas=[DirectivaCualitativa.desde_dict(d) for d in datos.get("directivas") or []],
            texto_prompt=datos.get("texto_prompt", ""),
        )


@dataclass
class EspecificacionArquitectonica:
    """PRD v2 §22.1. `params_generador` y `contexto_cualitativo` son
    compilados por la Fase D (todavía no implementada) — aquí solo existen
    como campos que la Fase D rellenará; por defecto están vacíos, nunca
    con un valor inventado."""

    especificacion_id: str
    version: int = 1
    sesion_entrevista_id: Optional[str] = None
    modo_origen: str = "entrevista_guiada"
    campos: list[CampoEspecificacion] = field(default_factory=list)
    params_generador: dict = field(default_factory=dict)
    contexto_cualitativo: Optional[ContextoCualitativo] = None
    decisiones_pendientes: list[str] = field(default_factory=list)
    creado_en: str = field(default_factory=_ahora)
    modificado_en: str = field(default_factory=_ahora)

    def __post_init__(self) -> None:
        _validar_enum(
            self.modo_origen, MODOS_ORIGEN_ESPECIFICACION, "modo_origen", "EspecificacionArquitectonica"
        )
        if self.version < 1:
            raise ValueError("EspecificacionArquitectonica.version debe ser >= 1")

    def a_dict(self) -> dict:
        return {
            "especificacion_id": self.especificacion_id,
            "version": self.version,
            "sesion_entrevista_id": self.sesion_entrevista_id,
            "modo_origen": self.modo_origen,
            "campos": _lista_a_dict(self.campos),
            "params_generador": dict(self.params_generador),
            "contexto_cualitativo": self.contexto_cualitativo.a_dict() if self.contexto_cualitativo else None,
            "decisiones_pendientes": list(self.decisiones_pendientes),
            "creado_en": self.creado_en,
            "modificado_en": self.modificado_en,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "EspecificacionArquitectonica":
        contexto = datos.get("contexto_cualitativo")
        return EspecificacionArquitectonica(
            especificacion_id=datos["especificacion_id"],
            version=int(datos.get("version", 1)),
            sesion_entrevista_id=datos.get("sesion_entrevista_id"),
            modo_origen=datos.get("modo_origen", "entrevista_guiada"),
            campos=[CampoEspecificacion.desde_dict(c) for c in datos.get("campos") or []],
            params_generador=dict(datos.get("params_generador") or {}),
            contexto_cualitativo=ContextoCualitativo.desde_dict(contexto) if contexto else None,
            decisiones_pendientes=list(datos.get("decisiones_pendientes") or []),
            creado_en=datos.get("creado_en") or _ahora(),
            modificado_en=datos.get("modificado_en") or _ahora(),
        )


# --- Traza de Generación --------------------------------------------------


@dataclass
class VerificacionDeterminista:
    """Contrato §6.3. Producida por `verificar_directivas_duras()` (Fase F,
    todavía no implementada), reutilizando `evaluator.py` — este módulo
    solo define la forma del resultado."""

    especificacion_id: str
    metodo: str
    resultado: str

    def __post_init__(self) -> None:
        _validar_enum(self.resultado, RESULTADOS_VERIFICACION, "resultado", "VerificacionDeterminista")

    def a_dict(self) -> dict:
        return {
            "especificacion_id": self.especificacion_id,
            "metodo": self.metodo,
            "resultado": self.resultado,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "VerificacionDeterminista":
        return VerificacionDeterminista(
            especificacion_id=datos["especificacion_id"],
            metodo=datos["metodo"],
            resultado=datos["resultado"],
        )


@dataclass
class RespuestaIAResumen:
    """`TrazaDeGeneracion.respuesta_ia` (contrato §6.3). `justificacion` es
    el texto libre que Claude ya devuelve hoy; `referencias_especificacion`
    es el campo opcional propuesto en PRD v2 §22.3 / contrato §9 — best
    effort, no fiable por sí solo (canal 1 de trazabilidad, §10 del
    contrato)."""

    justificacion: str
    referencias_especificacion: Optional[list[str]] = None

    def a_dict(self) -> dict:
        return {
            "justificacion": self.justificacion,
            "referencias_especificacion": self.referencias_especificacion,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "RespuestaIAResumen":
        return RespuestaIAResumen(
            justificacion=datos.get("justificacion", ""),
            referencias_especificacion=datos.get("referencias_especificacion"),
        )


@dataclass
class TrazaDeGeneracion:
    """Contrato §6.3, con dos campos añadidos aquí que el contrato no
    incluía porque en esa etapa no se persistía todavía (§6.3: "no se
    persiste en esta etapa"): `traza_id` (identificador propio, estable, del
    registro) y `proyecto_id` (a qué fila de `proyectos` pertenece — sin
    esto no habría forma de recuperarla, ver A6/A7 del plan). Se persiste
    desde la primera implementación (Decisión Pablo #2)."""

    traza_id: str
    especificacion_id: str
    proyecto_id: Optional[str] = None
    directivas_enviadas: list[DirectivaCualitativa] = field(default_factory=list)
    respuesta_ia: Optional[RespuestaIAResumen] = None
    verificaciones_deterministas: list[VerificacionDeterminista] = field(default_factory=list)
    # Fase F (integración con el generador), tarea D: el plan pide
    # explícitamente registrar "si hubo reintento" y "motivo del reintento"
    # — dos datos que el esquema de Fase A no preveía porque en esa etapa
    # `app.py:generar()` todavía no construía ninguna traza real. Extensión
    # aditiva mínima (campos opcionales con default, mismo criterio que
    # cualquier columna/campo nuevo del proyecto): no rompe ninguna traza
    # existente porque, a fecha de esta fase, `guardar_traza_generacion()`
    # nunca se había llamado todavía desde `app.py` — no hay ninguna fila
    # real que migrar. `motivo_reintento` es `None | "geometria" |
    # "directiva_dura" | "geometria+directiva_dura"` (ver
    # `ai_generator.generate_project`), nunca inventado por este módulo.
    reintento_disparado: bool = False
    motivo_reintento: Optional[str] = None
    creado_en: str = field(default_factory=_ahora)

    def a_dict(self) -> dict:
        return {
            "traza_id": self.traza_id,
            "especificacion_id": self.especificacion_id,
            "proyecto_id": self.proyecto_id,
            "directivas_enviadas": _lista_a_dict(self.directivas_enviadas),
            "respuesta_ia": self.respuesta_ia.a_dict() if self.respuesta_ia else None,
            "verificaciones_deterministas": _lista_a_dict(self.verificaciones_deterministas),
            "reintento_disparado": self.reintento_disparado,
            "motivo_reintento": self.motivo_reintento,
            "creado_en": self.creado_en,
        }

    @staticmethod
    def desde_dict(datos: dict) -> "TrazaDeGeneracion":
        respuesta_ia = datos.get("respuesta_ia")
        return TrazaDeGeneracion(
            traza_id=datos["traza_id"],
            especificacion_id=datos["especificacion_id"],
            proyecto_id=datos.get("proyecto_id"),
            directivas_enviadas=[
                DirectivaCualitativa.desde_dict(d) for d in datos.get("directivas_enviadas") or []
            ],
            respuesta_ia=RespuestaIAResumen.desde_dict(respuesta_ia) if respuesta_ia else None,
            verificaciones_deterministas=[
                VerificacionDeterminista.desde_dict(v) for v in datos.get("verificaciones_deterministas") or []
            ],
            reintento_disparado=bool(datos.get("reintento_disparado", False)),
            motivo_reintento=datos.get("motivo_reintento"),
            creado_en=datos.get("creado_en") or _ahora(),
        )


# --- Serialización a texto (para las columnas JSON de storage.py) --------


def volcar_estado(estado: EstadoEntrevista) -> str:
    return json.dumps(estado.a_dict(), sort_keys=True, ensure_ascii=False)


def cargar_estado(texto: str) -> EstadoEntrevista:
    return EstadoEntrevista.desde_dict(json.loads(texto))


def volcar_especificacion(especificacion: EspecificacionArquitectonica) -> str:
    return json.dumps(especificacion.a_dict(), sort_keys=True, ensure_ascii=False)


def cargar_especificacion(texto: str) -> EspecificacionArquitectonica:
    return EspecificacionArquitectonica.desde_dict(json.loads(texto))


def volcar_traza(traza: TrazaDeGeneracion) -> str:
    return json.dumps(traza.a_dict(), sort_keys=True, ensure_ascii=False)


def cargar_traza(texto: str) -> TrazaDeGeneracion:
    return TrazaDeGeneracion.desde_dict(json.loads(texto))
