"""Motor de entrevista — Fase C, tareas C2-C6, C10-C11.

Decide qué pregunta hacer, cuándo, cuándo no, qué depende de qué, cómo
detectar contradicciones, cuándo pedir aclaración y cuándo dejar de
preguntar. **100% determinista salvo el propio acto de llamar a Claude**
(delegado por completo en `claude_interprete.py` — este módulo nunca importa
`anthropic`).

Se ejecuta y se prueba sin Flask ni navegador: todas las funciones públicas
reciben y devuelven `EstadoEntrevista` (Fase A, `modelo.py`) más objetos
propios de este módulo, nunca un `request` ni una `Response`.

**Principio de aislamiento (igual que Fase A):** este módulo no importa
`analyzer.ai_generator`, no construye `params_generador`, no construye
`DirectivaCualitativa` ni `ContextoCualitativo` — eso es la Fase D
(compilador), todavía sin implementar. El motor solo produce
`RespuestaInterpretada` sobre el `EstadoEntrevista` que ya existía en la
Fase A; no toca el esquema aprobado de esa fase.

Principio rector (encargo de esta fase): el entrevistador se comporta como
un arquitecto júnior, no como un formulario de 15 preguntas — empieza
abierto, extrae lo que puede, pregunta solo lo que falta, adapta el orden a
lo que ya sabe, nunca pregunta dos veces lo mismo, nunca inventa, y termina
cuando hay información suficiente, no cuando se agotan N preguntas.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from .claude_interprete import InterpretacionError, InterpreteIA, ResultadoInterpretacion
from .modelo import (
    Contradiccion,
    EstadoEntrevista,
    RespuestaInterpretada,
    Turno,
    ValorEnConflicto,
    _ahora,
    nuevo_id,
)
from .preguntas import (
    CondicionActivacion,
    IMPRESCINDIBLES,
    PREGUNTAS,
    PREGUNTAS_BLOQUE_FIJO,
    PREGUNTAS_POR_ID,
    Pregunta,
)

# --- Límites (PRD v2 §21.4/§28, Decisión Pablo #4) --------------------------
#
# Deliberadamente NO son el criterio principal de parada (encargo de esta
# fase) — son un techo de seguridad. `evaluar_cierre()` solo los usa cuando
# los imprescindibles siguen sin resolver a pesar de haberlos alcanzado.

LIMITE_LLAMADAS_IA = 5
#: 25, no 20 (2026-08-15, "Materiales y Calidades"): el catálogo creció de 15+2 respaldos a 19+2+4
#: preguntas nuevas de materiales/fachadas/calidades -- un usuario que responde absolutamente todo (nunca
#: "no sé") ya necesita ~21 turnos (bloque fijo + 20 preguntas adaptativas) para agotar el catálogo entero,
#: por encima del límite anterior. Sigue siendo un techo de seguridad, no el criterio de parada normal
#: (`evaluar_cierre()` ya corta antes en el caso normal, en cuanto los imprescindibles están resueltos y no
#: quedan más candidatas) -- subirlo proporcionalmente evita que las preguntas nuevas queden inalcanzables
#: para el usuario más exhaustivo, sin cambiar el criterio de cuándo debería parar en el caso normal.
LIMITE_TURNOS = 25
AVISO_TURNOS_DESDE = 19


class InterpretacionRequeridaError(Exception):
    """`responder()` necesitaba interpretar texto libre y no se le pasó
    ningún `interprete` (ni pudo resolverse de forma determinista). Nunca se
    produce en el bloque adaptativo cerrado — solo puede ocurrir con
    preguntas `requiere_ia != "nunca"`."""


# --- Estructuras propias del motor (no persistidas por Fase A) -------------


@dataclass
class PreguntaSiguiente:
    """Lo que `siguiente_pregunta()` propone presentar. `preguntas` tiene 3
    elementos en el bloque fijo inicial, 1 en el adaptativo, y 0 cuando es
    una resolución de contradicción (ese caso no viene del catálogo)."""

    turno_id: str
    preguntas: tuple[Pregunta, ...]
    motivo: str
    es_resolucion_contradiccion: bool = False
    contradiccion_id: Optional[str] = None
    texto_resolucion: Optional[str] = None
    aviso: Optional[str] = None


@dataclass
class EventoLlamadaIA:
    """Instrumentación de coste (pedida explícitamente para los tests de
    esta fase): qué paso disparó la llamada, qué se extrajo, si de verdad
    se realizó (o se evitó por presupuesto agotado) y si, a criterio de una
    heurística explícita, podría haberse evitado con mejor determinismo."""

    paso: str
    motivo: str
    especificacion_ids_extraidos: list[str] = field(default_factory=list)
    realizada: bool = True
    evitable: bool = False


@dataclass
class ResultadoTurno:
    estado: EstadoEntrevista
    eventos_llamadas_ia: list[EventoLlamadaIA] = field(default_factory=list)


@dataclass
class ResultadoCierre:
    puede_cerrar: bool
    imprescindibles_pendientes: list[str] = field(default_factory=list)
    contradicciones_pendientes: list[str] = field(default_factory=list)
    limite_turnos_alcanzado: bool = False
    limite_llamadas_alcanzado: bool = False
    motivo: str = ""


# --- Ciclo de vida -----------------------------------------------------


def iniciar_entrevista(modo_entrada: str = "entrevista_guiada") -> EstadoEntrevista:
    return EstadoEntrevista(sesion_id=nuevo_id(), modo=modo_entrada, modo_entrada=modo_entrada)


#: Marcador de `RespuestaInterpretada.turno_id` para hechos sembrados desde fuera de la conversación (Paso
#: 0, "Mapa/Parcela Primero") -- nunca corresponde a un `Turno` real en `historial_turnos`, así que
#: `_preguntas_ya_realizadas`/`turnos_totales` no lo ven, pero `campo_tiene_respuesta` sí (le basta con que
#: exista en `respuestas_interpretadas`) -- exactamente lo que hace que la cola priorizada deje de proponer
#: cualquier pregunta que solo alimentara ese dato, sin fingir que hubo una pregunta y una respuesta reales.
TURNO_ID_SEMBRADO_EXTERNO = "sembrado_externo"


def sembrar_hecho_externo(estado: EstadoEntrevista, especificacion_id: str, valor: Any, motivo: str) -> None:
    """Marca `especificacion_id` como ya resuelto (Hecho) SIN pasar por `responder()` -- para datos que
    llegaron por una vía distinta a la conversación (2026-08-15, "omite las preguntas geográficas
    redundantes": Paso 0, mapa + Catastro real).

    Deliberadamente NO usa `interview_compilador.anadir_valores_expertos()`: esa función muta `estado.modo`
    a `"edicion_experta"` como efecto secundario, lo que corrompería una sesión `entrevista_guiada` real --
    hallazgo ya documentado en la tarea "Mapa/Parcela Primero" de esta misma sesión de trabajo.

    No crea ningún `Turno` (no hubo ninguna pregunta real) ni toca `turnos_totales`/`llamadas_ia_consumidas`
    -- un hecho sembrado no cuenta como turno de conversación. Si el campo ya tenía una respuesta, no hace
    nada (nunca sobrescribe en silencio, mismo principio que el resto del motor, PRD v2 §26)."""
    if campo_tiene_respuesta(estado, especificacion_id):
        return
    estado.respuestas_interpretadas.append(
        RespuestaInterpretada(
            respuesta_id=nuevo_id(), turno_id=TURNO_ID_SEMBRADO_EXTERNO, especificacion_id=especificacion_id,
            respuesta_cruda=valor, naturaleza="Hecho", valor=valor, motivo=motivo,
        )
    )
    estado.modificado_en = _ahora()


# --- Consultas sobre el estado (puras) --------------------------------------


def _contradiccion_pendiente(estado: EstadoEntrevista, especificacion_id: str) -> Optional[Contradiccion]:
    for c in estado.contradicciones:
        if c.especificacion_id == especificacion_id and not c.resuelta:
            return c
    return None


def campo_tiene_respuesta(estado: EstadoEntrevista, especificacion_id: str) -> bool:
    """Un campo cuenta como resuelto (Hecho o Hipótesis, PRD v2 §2) si tiene
    al menos una `RespuestaInterpretada` y no hay una contradicción sin
    resolver sobre él — mientras la tensión siga abierta, el campo NO está
    resuelto, aunque técnicamente tenga dos valores (principio: nunca se
    sobrescribe en silencio, PRD v2 §26)."""
    tiene = any(r.especificacion_id == especificacion_id for r in estado.respuestas_interpretadas)
    if not tiene:
        return False
    return _contradiccion_pendiente(estado, especificacion_id) is None


def _valor_actual(estado: EstadoEntrevista, especificacion_id: str) -> Any:
    for r in reversed(estado.respuestas_interpretadas):
        if r.especificacion_id == especificacion_id:
            return r.valor
    return None


def _preguntas_ya_realizadas(estado: EstadoEntrevista) -> set[str]:
    realizadas: set[str] = set()
    for t in estado.historial_turnos:
        realizadas.update(t.preguntas_ids)
    return realizadas


def _evalua_condicion(cond: CondicionActivacion, estado: EstadoEntrevista) -> bool:
    if cond.operador == "presente":
        return campo_tiene_respuesta(estado, cond.especificacion_id)
    if cond.operador == "ausente":
        return not campo_tiene_respuesta(estado, cond.especificacion_id)
    valor_actual = _valor_actual(estado, cond.especificacion_id)
    if cond.operador == "igual":
        return valor_actual == cond.valor
    if cond.operador == "distinto":
        return valor_actual != cond.valor
    if cond.operador == "en":
        return valor_actual in (cond.valor or ())
    if cond.operador == "no_en":
        return valor_actual not in (cond.valor or ())
    return False  # pragma: no cover - _validar_enum en CondicionActivacion ya lo impide


# --- Cola priorizada (C3) — árbol de decisión de la siguiente pregunta -----


def _candidatas_adaptativas(estado: EstadoEntrevista) -> list[Pregunta]:
    ya_realizadas = _preguntas_ya_realizadas(estado)
    candidatas = []
    for p in PREGUNTAS:
        if p.bloque != "adaptativo":
            continue
        if p.pregunta_id in ya_realizadas:
            continue  # principio: nunca preguntar dos veces lo mismo
        if p.condicion_activacion is not None and not _evalua_condicion(p.condicion_activacion, estado):
            continue  # C4: la rama no tomada nunca se pregunta
        if all(campo_tiene_respuesta(estado, i) for i in p.especificacion_ids):
            continue  # principio 6: evitar preguntas cuya respuesta ya se conoce/deriva
        candidatas.append(p)
    return candidatas


def _clave_prioridad(p: Pregunta, estado: EstadoEntrevista) -> tuple:
    """PRD v2 §25, en orden: (1) imprescindible sin resolver, (2)
    contradicción pendiente, (3) cuánto condiciona (nº de campos que
    todavía puede resolver), (4) coste de respuesta para el usuario."""
    imprescindible_sin_resolver = 0 if p.es_bloqueante(IMPRESCINDIBLES) else 1
    tiene_contradiccion = 0 if any(_contradiccion_pendiente(estado, i) for i in p.especificacion_ids) else 1
    campos_por_resolver = -len([i for i in p.especificacion_ids if not campo_tiene_respuesta(estado, i)])
    coste = (0 if p.tipo in ("opcion", "condicional") else 1) + (0 if p.requiere_ia == "nunca" else 1)
    return (imprescindible_sin_resolver, tiene_contradiccion, campos_por_resolver, coste)


def _fue_producida_por_ia(estado: EstadoEntrevista, respuesta: RespuestaInterpretada) -> bool:
    turno = next((t for t in estado.historial_turnos if t.turno_id == respuesta.turno_id), None)
    if turno is None:
        return False
    return any(
        PREGUNTAS_POR_ID[pid].requiere_ia != "nunca" for pid in turno.preguntas_ids if pid in PREGUNTAS_POR_ID
    )


def _campo_pendiente_reintento(estado: EstadoEntrevista) -> Optional[str]:
    """C9: solo imprescindibles, solo si la última respuesta vino de IA con
    confianza Baja, y solo si todavía no se ha reintentado ese campo (nunca
    más de una vez por dato)."""
    for especificacion_id in IMPRESCINDIBLES:
        respuestas_campo = [r for r in estado.respuestas_interpretadas if r.especificacion_id == especificacion_id]
        if not respuestas_campo:
            continue
        ultima = respuestas_campo[-1]
        if (
            ultima.naturaleza in ("Hipótesis", "Inferencia")
            and ultima.confianza == "Baja"
            and _fue_producida_por_ia(estado, ultima)
            and len(respuestas_campo) < 2
        ):
            return especificacion_id
    return None


def _preguntas_que_generaron(estado: EstadoEntrevista, especificacion_id: str) -> tuple[Pregunta, ...]:
    respuestas_campo = [r for r in estado.respuestas_interpretadas if r.especificacion_id == especificacion_id]
    if not respuestas_campo:
        return ()
    turno = next((t for t in estado.historial_turnos if t.turno_id == respuestas_campo[-1].turno_id), None)
    if turno is None:
        return ()
    return tuple(PREGUNTAS_POR_ID[pid] for pid in turno.preguntas_ids if pid in PREGUNTAS_POR_ID)


def _texto_resolucion(c: Contradiccion) -> str:
    valores = " / ".join(repr(v.valor) for v in c.valores_en_conflicto)
    return "Nos diste dos respuestas distintas sobre %r: %s — ¿cuál es la correcta?" % (
        c.especificacion_id,
        valores,
    )


def siguiente_pregunta(estado: EstadoEntrevista) -> Optional[PreguntaSiguiente]:
    """El árbol de decisión completo (C2-C5, C10 vía `_candidatas_adaptativas`
    que ya excluye lo resuelto). `None` significa "no hay nada más que
    preguntar" — puede ser porque ya hay información suficiente, o porque el
    límite de turnos se alcanzó; usar `evaluar_cierre()` para distinguirlo."""
    if estado.estado != "en_curso":
        return None
    if estado.turnos_totales >= LIMITE_TURNOS:
        return None  # cierre forzado — ver evaluar_cierre()

    pendientes = [c for c in estado.contradicciones if not c.resuelta]
    if pendientes:
        c = pendientes[0]
        return PreguntaSiguiente(
            turno_id=nuevo_id(), preguntas=(), motivo="resolver_contradiccion",
            es_resolucion_contradiccion=True, contradiccion_id=c.contradiccion_id,
            texto_resolucion=_texto_resolucion(c),
        )

    if not estado.historial_turnos:
        return PreguntaSiguiente(turno_id=nuevo_id(), preguntas=PREGUNTAS_BLOQUE_FIJO, motivo="bloque_fijo_inicial")

    campo_reintento = _campo_pendiente_reintento(estado)
    if campo_reintento is not None:
        preguntas_origen = _preguntas_que_generaron(estado, campo_reintento)
        if preguntas_origen:
            return PreguntaSiguiente(
                turno_id=nuevo_id(), preguntas=preguntas_origen,
                motivo="reintento_baja_confianza:%s" % campo_reintento,
            )

    candidatas = _candidatas_adaptativas(estado)
    if estado.llamadas_ia_consumidas >= LIMITE_LLAMADAS_IA:
        # §21.4: al agotar el presupuesto, solo preguntas deterministas.
        candidatas = [p for p in candidatas if p.requiere_ia == "nunca"]
    if not candidatas:
        return None

    mejor = min(candidatas, key=lambda p: _clave_prioridad(p, estado))
    aviso = None
    if estado.turnos_totales >= AVISO_TURNOS_DESDE:
        aviso = "Quedan como máximo %d turnos." % max(0, LIMITE_TURNOS - estado.turnos_totales)
    return PreguntaSiguiente(turno_id=nuevo_id(), preguntas=(mejor,), motivo="cola_priorizada", aviso=aviso)


# --- Reconocimiento determinista de "no sé" / delegación --------------------

_PATRONES_DESCONOCIDO = (
    "no se", "no lo se", "ni idea", "no lo tengo claro", "no lo tengo decidido", "sin decidir", "ns/nc",
)
_PATRONES_DELEGACION = (
    "decide tu", "decidelo tu", "lo que tu veas", "cualquiera", "elige tu", "decidid vosotros",
)


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, puntuación reducida a espacios y espacios
    colapsados — así "no sé, decide tú" y "no se decide tu" comparan igual,
    y un punto/coma pegado a una palabra no rompe el emparejamiento por
    subcadena de `_matchear_opcion`/`_es_desconocido`/`_es_delegacion`."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^a-z0-9 ]", " ", sin_acentos.lower())
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return " " + limpio + " "


#: Un texto largo que solo *menciona* "no sé" de pasada dentro de una
#: respuesta elaborada no es lo mismo que un "no sé" como respuesta
#: completa (escenario 3: "algo bonito pero no sé explicarlo bien, que se
#: sienta como en casa" es información real, no una no-respuesta) — el
#: umbral de longitud es lo que distingue ambos casos.
_MAX_PALABRAS_RESPUESTA_CORTA = 6


def _es_desconocido(texto: Optional[str]) -> bool:
    if texto is None:
        return True
    normalizado = _normalizar(texto)
    contenido = normalizado.strip()
    if contenido == "":
        return True
    if len(contenido.split()) > _MAX_PALABRAS_RESPUESTA_CORTA:
        return False
    return any((" " + p + " ") in normalizado for p in _PATRONES_DESCONOCIDO)


def _es_delegacion(texto: Optional[str]) -> bool:
    if texto is None:
        return False
    normalizado = _normalizar(texto)
    if len(normalizado.strip().split()) > _MAX_PALABRAS_RESPUESTA_CORTA:
        return False
    return any(p in normalizado for p in _PATRONES_DELEGACION)


def _hipotesis_desconocido(pregunta: Pregunta, turno_id: str, raw: Optional[str]) -> list[RespuestaInterpretada]:
    return [
        RespuestaInterpretada(
            respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=especificacion_id,
            respuesta_cruda=raw, naturaleza="Hipótesis", valor=None, confianza="Baja",
            motivo="el usuario no lo sabe o no respondió",
        )
        for especificacion_id in pregunta.especificacion_ids
    ]


# --- Sinónimos de las preguntas cerradas (matcher determinista, C1/C2) -----
#
# Diccionario de datos, no de código por pregunta: el emparejamiento en sí
# (`_matchear_opcion`) es una única función genérica que usa esta tabla.

_SINONIMOS_OPCIONES: dict[str, dict[str, tuple[str, ...]]] = {
    "p2": {
        "vivir": ("vivir", "para mi", "residencia propia"),
        "vender": ("vender",),
        "alquilar": ("alquilar", "arrendar"),
        "no_lo_sabe": ("no lo se", "no se", "aun no", "todavia no"),
    },
    "p3": {
        "tengo_parcela": ("tengo la parcela", "ya tengo", "si la tengo", "tengo parcela"),
        "buscando_parcela": ("buscando", "imaginando", "no la tengo", "todavia la estoy"),
    },
    "p6": {
        "mas_grandes_menos_viviendas": ("mas grandes", "muy grandes", "grandes y menos"),
        "mas_pequenas_mas_viviendas": (
            "mas pequenas", "pequenas y mas", "maximo numero", "el maximo posible", "cuantas mas mejor",
        ),
    },
    "p8": {
        "norte": ("norte",), "sur": ("sur",), "este": ("este",), "oeste": ("oeste",),
        "noreste": ("noreste", "nor-este"), "noroeste": ("noroeste", "nor-oeste"),
        "sureste": ("sureste", "sur-este"), "suroeste": ("suroeste", "sur-oeste"),
        "combinacion": ("combinacion", "varias orientaciones"),
    },
    "p10": {
        "ahorro_energetico_largo_plazo": ("ahorro", "factura energetica", "largo plazo"),
        "coste_construccion_bajo": ("coste de construccion", "barato ahora", "coste bajo"),
    },
    "p12": {
        "mucha": ("mucha", "bastante privacidad"),
        "normal": ("normal", "la normal"),
        "le_da_igual": ("me da igual", "te da igual", "da igual", "indiferente"),
    },
    "p13": {
        "no_lo_sabe": ("no lo se", "no se sabe", "no sabemos"),
        "si": ("si",),
        "no": ("no",),
    },
    "p14": {
        "espacio_exterior_propio": ("espacio exterior propio", "terraza propia", "propio espacio"),
        "aprovechar_metros_interiores": ("aprovechar", "metros interiores", "por dentro"),
    },
    "p15": {
        "abierta": ("abierta", "integrada", "americana"),
        "cerrada": ("cerrada", "separada"),
    },
    "p_tipologia_directa": {
        "unifamiliar": ("unifamiliar", "una vivienda", "casa individual"),
        "plurifamiliar": ("plurifamiliar", "varias viviendas", "edificio de pisos", "bloque"),
        "otra": ("otra", "otro tipo"),
    },
}


def _matchear_opcion(pregunta: Pregunta, raw: Optional[str]) -> Optional[str]:
    if raw is None or not pregunta.opciones:
        return None
    texto = _normalizar(raw)
    sinonimos = _SINONIMOS_OPCIONES.get(pregunta.pregunta_id, {})
    mejor_opcion, mejor_longitud = None, -1
    for opcion in pregunta.opciones:
        for candidato in sinonimos.get(opcion, (opcion,)):
            candidato_normalizado = _normalizar(candidato)
            if candidato_normalizado in texto and len(candidato_normalizado) > mejor_longitud:
                mejor_opcion, mejor_longitud = opcion, len(candidato_normalizado)
    return mejor_opcion


# --- Procesamiento determinista de una respuesta (sin Claude) --------------

_RE_NUMERO = re.compile(r"\d[\d.,]*")


def _parsear_numero_es(fragmento: str) -> float:
    """`.` como separador de miles, `,` como decimal (convención española) —
    "1.200" -> 1200.0, "800,5" -> 800.5, "800" -> 800.0."""
    return float(fragmento.replace(".", "").replace(",", "."))


def _procesar_determinista(pregunta: Pregunta, raw: Optional[str], turno_id: str) -> list[RespuestaInterpretada]:
    def _hecho(especificacion_id: str, valor: Any, motivo: Optional[str] = None) -> RespuestaInterpretada:
        return RespuestaInterpretada(
            respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=especificacion_id,
            respuesta_cruda=raw, naturaleza="Hecho", valor=valor, confianza=None, motivo=motivo,
        )

    def _hipotesis_baja(especificacion_id: str, motivo: str) -> RespuestaInterpretada:
        return RespuestaInterpretada(
            respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=especificacion_id,
            respuesta_cruda=raw, naturaleza="Hipótesis", valor=None, confianza="Baja", motivo=motivo,
        )

    if pregunta.tipo in ("opcion", "condicional") and pregunta.opciones:
        opcion = _matchear_opcion(pregunta, raw)
        if opcion is not None:
            return [_hecho(i, opcion) for i in pregunta.especificacion_ids]
        if pregunta.tipo == "condicional" and (raw or "").strip() and not _es_delegacion(raw):
            # Las condicionales (p3, p8) admiten texto libre fuera del
            # vocabulario cerrado — p. ej. una dirección para la 8.
            texto = raw.strip()
            return [
                _hecho(i, texto, motivo="respuesta libre fuera del vocabulario cerrado, almacenada tal cual")
                for i in pregunta.especificacion_ids
            ]
        return [_hipotesis_baja(i, "respuesta no reconocida entre las opciones esperadas") for i in pregunta.especificacion_ids]

    # Abiertas deterministas (requiere_ia == "nunca") con parseo específico.
    if pregunta.pregunta_id == "p3_forma" and _es_delegacion(raw):
        return [
            _hecho(i, "irregular_decidido_por_sistema", motivo="el usuario delega la forma del solar en el sistema (PRD v2 §2.4)")
            for i in pregunta.especificacion_ids
        ]

    if pregunta.pregunta_id == "p3_superficie":
        m = _RE_NUMERO.search(raw or "")
        if m:
            return [_hecho(i, _parsear_numero_es(m.group(0))) for i in pregunta.especificacion_ids]
        return [_hipotesis_baja(i, "no se pudo extraer un número de la respuesta") for i in pregunta.especificacion_ids]

    if pregunta.pregunta_id == "p7":
        m = _RE_NUMERO.search(raw or "")
        if m:
            return [_hecho(i, int(_parsear_numero_es(m.group(0)))) for i in pregunta.especificacion_ids]
        return [_hipotesis_baja(i, "sin verificación normativa municipal disponible") for i in pregunta.especificacion_ids]

    # Resto de abiertas deterministas (p3_ciudad y cualquier futura de este tipo): texto libre tal cual.
    texto = (raw or "").strip()
    return [_hecho(i, texto) for i in pregunta.especificacion_ids]


def _intentar_determinista_condicional(
    pregunta: Pregunta, raw: Optional[str], turno_id: str
) -> Optional[list[RespuestaInterpretada]]:
    """p9/p11 (`requiere_ia == "condicional"`): un parseo determinista
    simple que solo tiene éxito cuando la respuesta ya viene en forma clara
    — PRD v2 §21.2: "0 [llamadas] si el usuario responde con cifras/opciones
    simples". `None` significa "no se pudo, hace falta Claude"."""
    texto = (raw or "").strip()
    if not texto:
        return None
    if pregunta.pregunta_id == "p9" and _RE_NUMERO.search(texto):
        return [
            RespuestaInterpretada(
                respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=i, respuesta_cruda=raw,
                naturaleza="Hecho", valor=texto, confianza=None,
                motivo="cifra/horquilla reconocida directamente, sin necesidad de interpretación",
            )
            for i in pregunta.especificacion_ids
        ]
    if pregunta.pregunta_id == "p11" and len(texto.split()) <= 4:
        return [
            RespuestaInterpretada(
                respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=i, respuesta_cruda=raw,
                naturaleza="Hecho", valor=texto, confianza=None,
                motivo="referencia breve y directa, almacenada tal cual sin necesidad de interpretación",
            )
            for i in pregunta.especificacion_ids
        ]
    return None


# --- Contradicciones (C6, deterministas; semánticas via claude_interprete) -


def _detectar_contradiccion_directa(estado: EstadoEntrevista, nueva: RespuestaInterpretada) -> Optional[Contradiccion]:
    if nueva.valor is None:
        return None  # una Hipótesis "no sé" no contradice nada
    if _contradiccion_pendiente(estado, nueva.especificacion_id) is not None:
        return None  # ya hay una tensión abierta en este campo; no dupliques
    for anterior in estado.respuestas_interpretadas:
        if anterior.especificacion_id != nueva.especificacion_id or anterior.valor is None:
            continue
        if anterior.valor != nueva.valor:
            return Contradiccion(
                contradiccion_id=nuevo_id(), especificacion_id=nueva.especificacion_id,
                valores_en_conflicto=[
                    ValorEnConflicto(turno_id=anterior.turno_id, valor=anterior.valor),
                    ValorEnConflicto(turno_id=nueva.turno_id, valor=nueva.valor),
                ],
            )
    return None


def _registrar_contradiccion_semantica(estado: EstadoEntrevista, deteccion: tuple[str, Any], turno_id: str) -> None:
    """C8: la contradicción semántica que Claude señala en la MISMA llamada
    que interpreta el bloque adaptativo abierto — nunca una llamada aparte
    (Decisión Pablo #5)."""
    especificacion_id, valor_conflictivo = deteccion
    if _contradiccion_pendiente(estado, especificacion_id) is not None:
        return
    anteriores = [r for r in estado.respuestas_interpretadas if r.especificacion_id == especificacion_id]
    valor_anterior = anteriores[-1].valor if anteriores else None
    turno_anterior = anteriores[-1].turno_id if anteriores else turno_id
    estado.contradicciones.append(
        Contradiccion(
            contradiccion_id=nuevo_id(), especificacion_id=especificacion_id,
            valores_en_conflicto=[
                ValorEnConflicto(turno_id=turno_anterior, valor=valor_anterior),
                ValorEnConflicto(turno_id=turno_id, valor=valor_conflictivo),
            ],
        )
    )


def _resolver_contradiccion_interna(estado: EstadoEntrevista, contradiccion_id: str, valor_elegido: Any, turno_id: str) -> None:
    contradiccion = next((c for c in estado.contradicciones if c.contradiccion_id == contradiccion_id), None)
    if contradiccion is None:
        raise ValueError("contradiccion_id desconocido: %r" % (contradiccion_id,))
    contradiccion.resuelta = True
    contradiccion.valor_resuelto = valor_elegido
    contradiccion.resuelta_en_turno_id = turno_id
    estado.respuestas_interpretadas.append(
        RespuestaInterpretada(
            respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=contradiccion.especificacion_id,
            respuesta_cruda=valor_elegido, naturaleza="Hecho", valor=valor_elegido, confianza=None,
            motivo="resuelto por el usuario tras una contradicción",
        )
    )


# --- responder(): procesa un turno completo ---------------------------------


def _registrar_no_negociable(estado: EstadoEntrevista, respuesta: RespuestaInterpretada) -> None:
    if respuesta.especificacion_id != "prioridades.no_negociables":
        return
    texto = respuesta.valor if isinstance(respuesta.valor, str) else respuesta.respuesta_cruda
    if isinstance(texto, str) and texto.strip() and texto not in estado.no_negociables:
        estado.no_negociables.append(texto.strip())


def responder(
    estado: EstadoEntrevista,
    pregunta_siguiente: PreguntaSiguiente,
    respuestas_crudas: dict[str, Any],
    interprete: Optional[InterpreteIA] = None,
) -> ResultadoTurno:
    """Procesa las respuestas a un turno propuesto por `siguiente_pregunta()`.

    `interprete` solo se toca (y por tanto solo se construye/llama en el
    caso real) cuando alguna de las preguntas del turno de verdad lo
    necesita — un turno compuesto solo por preguntas cerradas nunca lo
    invoca ni falla si es `None` (C20/C12: determinismo cuando Claude no
    interviene)."""
    if estado.estado != "en_curso":
        raise ValueError("No se puede responder: la entrevista no está en curso (estado=%r)" % (estado.estado,))

    if pregunta_siguiente.es_resolucion_contradiccion:
        turno = Turno(
            turno_id=pregunta_siguiente.turno_id, preguntas_ids=[],
            respuesta_cruda={
                "contradiccion_id": pregunta_siguiente.contradiccion_id,
                "valor_elegido": respuestas_crudas.get("valor_elegido"),
            },
        )
        estado.historial_turnos.append(turno)
        estado.turnos_totales += 1
        _resolver_contradiccion_interna(
            estado, pregunta_siguiente.contradiccion_id, respuestas_crudas.get("valor_elegido"), turno.turno_id
        )
        estado.modificado_en = _ahora()
        return ResultadoTurno(estado=estado, eventos_llamadas_ia=[])

    preguntas = pregunta_siguiente.preguntas
    turno = Turno(
        turno_id=pregunta_siguiente.turno_id,
        preguntas_ids=[p.pregunta_id for p in preguntas],
        respuesta_cruda={p.pregunta_id: respuestas_crudas.get(p.pregunta_id) for p in preguntas},
    )
    estado.historial_turnos.append(turno)
    estado.turnos_totales += 1

    eventos: list[EventoLlamadaIA] = []
    nuevas: list[RespuestaInterpretada] = []

    conjunta = [p for p in preguntas if p.requiere_ia == "siempre"]
    individuales = [p for p in preguntas if p.requiere_ia != "siempre"]

    if conjunta:
        textos = {p.pregunta_id: (respuestas_crudas.get(p.pregunta_id) or "") for p in conjunta}
        if all(_es_desconocido(v) for v in textos.values()):
            for p in conjunta:
                nuevas.extend(_hipotesis_desconocido(p, turno.turno_id, textos[p.pregunta_id]))
        elif estado.llamadas_ia_consumidas >= LIMITE_LLAMADAS_IA:
            eventos.append(EventoLlamadaIA(
                paso="bloque_fijo", motivo="presupuesto de llamadas IA agotado, no se interpreta",
                realizada=False,
            ))
            for p in conjunta:
                for i in p.especificacion_ids:
                    nuevas.append(RespuestaInterpretada(
                        respuesta_id=nuevo_id(), turno_id=turno.turno_id, especificacion_id=i,
                        respuesta_cruda=textos.get(p.pregunta_id), naturaleza="Hipótesis", confianza="Baja",
                        motivo="límite de llamadas IA alcanzado, no se ha podido interpretar",
                    ))
        elif interprete is None:
            raise InterpretacionRequeridaError(
                "El bloque fijo necesita interpretación de Claude; pasa un `interprete`."
            )
        else:
            eventos.append(_llamar_bloque_fijo(estado, interprete, textos, turno.turno_id, nuevas))

    for p in individuales:
        raw = respuestas_crudas.get(p.pregunta_id)
        if _es_desconocido(raw):
            nuevas.extend(_hipotesis_desconocido(p, turno.turno_id, raw))
            continue
        if p.requiere_ia == "nunca":
            nuevas.extend(_procesar_determinista(p, raw, turno.turno_id))
            continue
        # requiere_ia == "condicional"
        parseo = _intentar_determinista_condicional(p, raw, turno.turno_id)
        if parseo is not None:
            nuevas.extend(parseo)
            continue
        if estado.llamadas_ia_consumidas >= LIMITE_LLAMADAS_IA:
            eventos.append(EventoLlamadaIA(
                paso="bloque_adaptativo_abierto", motivo="presupuesto de llamadas IA agotado, no se interpreta %s" % p.pregunta_id,
                realizada=False,
            ))
            for i in p.especificacion_ids:
                nuevas.append(RespuestaInterpretada(
                    respuesta_id=nuevo_id(), turno_id=turno.turno_id, especificacion_id=i, respuesta_cruda=raw,
                    naturaleza="Hipótesis", confianza="Baja",
                    motivo="límite de llamadas IA alcanzado, no se ha podido interpretar",
                ))
            continue
        if interprete is None:
            raise InterpretacionRequeridaError(
                "La pregunta %r necesita interpretación de Claude; pasa un `interprete`." % p.pregunta_id
            )
        eventos.append(_llamar_texto_libre(estado, interprete, p, raw, turno.turno_id, nuevas))

    for nueva in nuevas:
        conflicto = _detectar_contradiccion_directa(estado, nueva)
        if conflicto is not None:
            estado.contradicciones.append(conflicto)
        estado.respuestas_interpretadas.append(nueva)
        _registrar_no_negociable(estado, nueva)

    estado.modificado_en = _ahora()
    return ResultadoTurno(estado=estado, eventos_llamadas_ia=eventos)


def _llamar_bloque_fijo(
    estado: EstadoEntrevista, interprete: InterpreteIA, textos: dict[str, str], turno_id: str,
    nuevas: list[RespuestaInterpretada],
) -> EventoLlamadaIA:
    try:
        resultado: ResultadoInterpretacion = interprete.interpretar_bloque_fijo(textos, turno_id)
        estado.llamadas_ia_consumidas += 1
        nuevas.extend(resultado.respuestas)
        if resultado.contradiccion_detectada:
            _registrar_contradiccion_semantica(estado, resultado.contradiccion_detectada, turno_id)
        return EventoLlamadaIA(
            paso="bloque_fijo", motivo="interpretación conjunta de p1/p4/p5",
            especificacion_ids_extraidos=[r.especificacion_id for r in resultado.respuestas],
            realizada=True, evitable=all(len(t.split()) <= 3 for t in textos.values() if t),
        )
    except InterpretacionError as exc:
        estado.llamadas_ia_consumidas += 1  # el intento cuenta para el presupuesto
        for p in PREGUNTAS_BLOQUE_FIJO:
            nuevas.extend(_hipotesis_fallo(p, turno_id, textos.get(p.pregunta_id), exc))
        return EventoLlamadaIA(paso="bloque_fijo", motivo="fallo de interpretación: %s" % exc, realizada=True)


def _llamar_texto_libre(
    estado: EstadoEntrevista, interprete: InterpreteIA, p: Pregunta, raw: Any, turno_id: str,
    nuevas: list[RespuestaInterpretada],
) -> EventoLlamadaIA:
    try:
        resultado: ResultadoInterpretacion = interprete.interpretar_texto_libre(p, raw, turno_id)
        estado.llamadas_ia_consumidas += 1
        nuevas.extend(resultado.respuestas)
        if resultado.contradiccion_detectada:
            _registrar_contradiccion_semantica(estado, resultado.contradiccion_detectada, turno_id)
        return EventoLlamadaIA(
            paso="bloque_adaptativo_abierto", motivo="interpretación de %s" % p.pregunta_id,
            especificacion_ids_extraidos=[r.especificacion_id for r in resultado.respuestas], realizada=True,
        )
    except InterpretacionError as exc:
        estado.llamadas_ia_consumidas += 1
        nuevas.extend(_hipotesis_fallo(p, turno_id, raw, exc))
        return EventoLlamadaIA(paso="bloque_adaptativo_abierto", motivo="fallo de interpretación: %s" % exc, realizada=True)


def _hipotesis_fallo(pregunta: Pregunta, turno_id: str, raw: Any, exc: Exception) -> list[RespuestaInterpretada]:
    return [
        RespuestaInterpretada(
            respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=i, respuesta_cruda=raw,
            naturaleza="Hipótesis", confianza="Baja", motivo="fallo de interpretación de IA: %s" % exc,
        )
        for i in pregunta.especificacion_ids
    ]


def responder_contradiccion(estado: EstadoEntrevista, contradiccion_id: str, valor_elegido: Any) -> ResultadoTurno:
    """Atajo de `responder()` para tests/llamadas directas que no quieren
    fabricar un `PreguntaSiguiente` a mano."""
    ps = PreguntaSiguiente(
        turno_id=nuevo_id(), preguntas=(), motivo="resolver_contradiccion",
        es_resolucion_contradiccion=True, contradiccion_id=contradiccion_id,
    )
    return responder(estado, ps, {"valor_elegido": valor_elegido})


# --- Deshacer el último turno ("Anterior") -- 2026-08-15, a petición explícita ---------------------------


def _recalcular_no_negociables(estado: EstadoEntrevista) -> None:
    """`no_negociables` es una lista DERIVADA de `respuestas_interpretadas` (ver `_registrar_no_negociable`),
    no un registro independiente -- tras deshacer un turno, se reconstruye entera a partir de lo que quede,
    en vez de intentar deshacer un único `append` a mano (mismo predicado exacto que `_registrar_no_
    negociable`, para que el resultado sea idéntico al que habría si esas respuestas nunca hubiesen
    incluido el turno deshecho)."""
    resultado: list[str] = []
    for r in estado.respuestas_interpretadas:
        if r.especificacion_id != "prioridades.no_negociables":
            continue
        texto = r.valor if isinstance(r.valor, str) else r.respuesta_cruda
        if isinstance(texto, str) and texto.strip() and texto not in resultado:
            resultado.append(texto.strip())
    estado.no_negociables = resultado


def puede_deshacer(estado: EstadoEntrevista) -> bool:
    """Hay algo que deshacer si la entrevista sigue en curso y ya se respondió al menos un turno real --
    "Anterior" en el primer paso no tiene ningún turno al que volver (mismo criterio que pide el encargo:
    deshabilitado únicamente en el primer paso)."""
    return estado.estado == "en_curso" and bool(estado.historial_turnos)


def deshacer_ultimo_turno(estado: EstadoEntrevista) -> EstadoEntrevista:
    """Deshace el turno más reciente -- botón "Anterior" (a petición explícita, 2026-08-15). Revierte
    EXACTAMENTE lo que ese turno produjo, nunca una reconstrucción aproximada ni más de un turno a la vez:

    - Saca el `Turno` de `historial_turnos` (vuelve a ser una pregunta "no realizada todavía" para
      `_preguntas_ya_realizadas`) y decrementa `turnos_totales` en consecuencia (siempre van 1:1, ver cómo
      `responder()` los incrementa juntos).
    - Quita toda `RespuestaInterpretada` que ese turno produjo -- el/los campo(s) que respondía vuelven a
      estar sin resolver, así `siguiente_pregunta()` puede volver a proponer la misma pregunta con el mismo
      criterio de prioridad de siempre (nunca se fuerza a mano cuál es "la anterior").
    - Si el turno era la resolución de una contradicción, la reabre tal cual estaba (`resuelta=False`, sin
      valor resuelto) en vez de dejarla resuelta con una respuesta huérfana.
    - Si el turno fue el que CREÓ una contradicción todavía sin resolver (el lado nuevo del conflicto), esa
      `Contradiccion` deja de tener sentido sin la respuesta que la originó -- se elimina entera, nunca se
      deja un conflicto fantasma bloqueando el cierre para siempre.
    - `no_negociables` se recalcula desde cero (`_recalcular_no_negociables`) a partir de lo que quede.
    - Deliberadamente NO se toca `llamadas_ia_consumidas`: el presupuesto de llamadas a IA ya gastado no se
      devuelve, para que "Anterior" + "Continuar" repetidos no sean una forma de resetear ese límite --
      limitación conocida y documentada (ver informe de cierre de esta tarea), no un descuido: si el turno
      deshecho consumió una llamada, esa llamada ya sucedió de verdad, cuesta dinero real.

    No hace falta ningún `interprete` de Claude: es la operación inversa exacta de lo que `responder()` ya
    escribió, nunca una interpretación nueva."""
    if not puede_deshacer(estado):
        raise ValueError("No hay ningún turno que deshacer.")
    turno = estado.historial_turnos.pop()
    estado.turnos_totales = max(0, estado.turnos_totales - 1)
    estado.respuestas_interpretadas = [
        r for r in estado.respuestas_interpretadas if r.turno_id != turno.turno_id
    ]
    for c in estado.contradicciones:
        if c.resuelta_en_turno_id == turno.turno_id:
            c.resuelta = False
            c.valor_resuelto = None
            c.resuelta_en_turno_id = None
    estado.contradicciones = [
        c for c in estado.contradicciones
        if not any(v.turno_id == turno.turno_id for v in c.valores_en_conflicto)
    ]
    _recalcular_no_negociables(estado)
    estado.modificado_en = _ahora()
    return estado


# --- Criterio de parada (C11) ------------------------------------------


def estimar_pasos_totales(estado: EstadoEntrevista) -> int:
    """Estimación honesta y DINÁMICA del número total de turnos que hará falta completar -- nunca un número
    fijo tipo "8" (bug reportado en vivo, 2026-08-15: el contador de la UI se quedaba clavado en "8/8"
    aunque la entrevista seguía pidiendo preguntas opcionales después de resolver los 8 imprescindibles).

    Se recalcula en cada turno a partir de la MISMA cola priorizada que ya decide qué preguntar
    (`_candidatas_adaptativas`): si una pregunta se salta (activación condicional que no aplica, ya resuelta
    por el Paso 0/mapa vía `sembrar_hecho_externo`, presupuesto de llamadas IA agotado...), deja de contar
    aquí también, automáticamente, sin ningún cálculo aparte que pueda desincronizarse de la lógica real.

    No es una promesa exacta -- una contradicción nueva puede añadir un turno que esta estimación no
    preveía -- es una ESTIMACIÓN, igual que cualquier barra de progreso de un proceso adaptativo con
    ramificaciones; se reajusta sola en el siguiente turno, nunca se queda clavada."""
    turnos_restantes = len(_candidatas_adaptativas(estado))
    if not estado.historial_turnos:
        turnos_restantes += 1  # el propio bloque fijo inicial, todavía sin responder
    return estado.turnos_totales + turnos_restantes


def evaluar_cierre(estado: EstadoEntrevista) -> ResultadoCierre:
    """Función pura, sin Flask ni Claude. Los imprescindibles y las
    contradicciones son el criterio PRINCIPAL; los límites de turnos/llamadas
    son un techo de seguridad, nunca el motivo por el que se cierra una
    entrevista que ya tiene información suficiente."""
    imprescindibles_pendientes = [i for i in IMPRESCINDIBLES if not campo_tiene_respuesta(estado, i)]
    contradicciones_pendientes = [c.contradiccion_id for c in estado.contradicciones if not c.resuelta]
    limite_turnos = estado.turnos_totales >= LIMITE_TURNOS
    limite_llamadas = estado.llamadas_ia_consumidas >= LIMITE_LLAMADAS_IA

    if contradicciones_pendientes:
        return ResultadoCierre(
            False, imprescindibles_pendientes, contradicciones_pendientes, limite_turnos, limite_llamadas,
            motivo="hay contradicciones sin resolver",
        )
    if not imprescindibles_pendientes:
        return ResultadoCierre(
            True, [], [], limite_turnos, limite_llamadas,
            motivo="todos los imprescindibles están resueltos (Hecho o Hipótesis)",
        )
    if limite_turnos:
        return ResultadoCierre(
            True, imprescindibles_pendientes, [], limite_turnos, limite_llamadas,
            motivo="límite de turnos alcanzado; cierre forzado con lo disponible, sin inventar nada",
        )
    return ResultadoCierre(
        False, imprescindibles_pendientes, [], limite_turnos, limite_llamadas,
        motivo="quedan imprescindibles por resolver",
    )


def puede_cerrar(estado: EstadoEntrevista) -> bool:
    """`puede_cerrar(estado) -> bool`, tal como pide el criterio de
    aceptación de C11 — versión reducida de `evaluar_cierre()` para quien
    solo necesita la decisión binaria."""
    return evaluar_cierre(estado).puede_cerrar


def cerrar_entrevista(estado: EstadoEntrevista, forzado: bool = False) -> EstadoEntrevista:
    resultado = evaluar_cierre(estado)
    if not resultado.puede_cerrar and not forzado:
        raise ValueError("La entrevista no cumple el criterio de cierre todavía: %s" % resultado.motivo)
    estado.estado = "cerrada"
    estado.modificado_en = _ahora()
    return estado
