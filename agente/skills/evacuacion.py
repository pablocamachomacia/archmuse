# -*- coding: utf-8 -*-
"""Skill: comprobación de la longitud de los recorridos de evacuación.

Atiende la mitad comprobable de «analiza este proyecto y dime qué problemas
tiene»: coge una longitud **medida**, el umbral **citado** del DB-SI y los
compara. Nada más.

**Por qué esta comprobación y no otra.** Porque es la única del corpus actual
que se puede hacer entera con una cita oficial detrás de cada número. Escribir
hoy una Skill de «revisión general del proyecto» sería exactamente lo que este
repositorio tiene escrito que no hay que hacer: un informe que se lee como
completo sobre un corpus que cubre una regla.

**Dónde está la frontera con el criterio profesional**, que es lo que D-7 de
`docs/design/decisiones-pendientes.md` deja bloqueado. Esta Skill **no** decide
si un recorrido es razonable, ni propone por dónde llevarlo, ni juzga el
proyecto: resta dos números y dice de dónde salió cada uno. La longitud la mide
el arquitecto y la declara; el umbral lo pone el BOE. Si alguna vez esta Skill
empieza a recomendar trazados, deja de ser esto y necesita validación colegiada.

**Y una limitación que se declara alto:** la regla piloto del corpus está
`pendiente_de_firma_colegiada`. El veredicto es provisional por construcción, y
viaja diciéndolo.
"""
from __future__ import annotations

from typing import List

from analyzer.hechos import Motivo

from ..afirmacion import Afirmacion, calculo
from ..skill import Requisito, ResultadoDeSkill, Skill
from ..verificacion import Verificacion, valor_dentro_de

CID = "es.rd_314_2006.seguridad_incendio.longitud_recorrido_evacuacion"

CLAVE_LONGITUD = "evacuacion.longitud_recorrido_m"
CLAVE_SALIDAS = "evacuacion.numero_salidas"
CLAVE_CONDICION = "evacuacion.condicion"

PRODUCE = ("evacuacion.umbral_m", "evacuacion.holgura_m", "evacuacion.cumple")


def _desconocidas(claves, motivo: Motivo, fuente: str) -> List[Afirmacion]:
    return [
        Afirmacion(nombre=c, naturaleza="hecho", valor=None, estado="UNKNOWN",
                   origen="observado", fuente=fuente, motivo=motivo)
        for c in claves
    ]


def _ejecutar(ctx) -> ResultadoDeSkill:
    afirmaciones: List[Afirmacion] = []
    no_hecho: List[str] = []
    preguntas: List[str] = []

    ambito = ctx.invocar("territorial.resolver_ambito",
                         municipio=ctx.valor("territorial.municipio"))
    if not ambito.get("ok"):
        motivo = Motivo(codigo=ambito.get("error", "ambito_irresoluble"),
                        detalle=ambito.get("detalle", ""))
        if ambito.get("pregunta"):
            preguntas.append(ambito["pregunta"])
        return ResultadoDeSkill(
            afirmaciones=tuple(_desconocidas(PRODUCE, motivo, ctx.firma)),
            preguntas=tuple(preguntas),
            no_hecho=("no se ha podido situar el proyecto territorialmente",),
        )

    # Se pregunta primero qué rige, y solo después cuánto. Al revés se resolvería
    # un umbral de una regla que a lo mejor no aplica a este proyecto.
    aplicables = ctx.invocar(
        "normativa.reglas_aplicables",
        codigo_municipio=ambito["codigo_municipio"],
        uso=ctx.valor("proyecto.uso"),
        tipologia=ctx.valor("proyecto.tipologia"),
        **({"fecha_devengo": ctx.valor("proyecto.fecha_devengo")}
           if ctx.valor("proyecto.fecha_devengo") else {}),
    )
    regla = None
    if aplicables.get("ok"):
        regla = next((n for n in aplicables["normas"] if n["concept_id"] == CID), None)
    if regla is None:
        motivo = Motivo(
            codigo="regla_no_aplicable_o_ausente",
            detalle=("la regla de longitud de recorridos de evacuación no consta como "
                     "aplicable a este proyecto en el corpus cargado"),
        )
        return ResultadoDeSkill(
            afirmaciones=tuple(_desconocidas(PRODUCE, motivo, ctx.firma)),
            no_hecho=("no se ha comprobado la evacuación: la regla no consta aplicable",),
        )
    if regla["estado"] == "no_aplica":
        motivo = Motivo(codigo="no_aplica", detalle=regla["motivo"])
        return ResultadoDeSkill(
            afirmaciones=tuple(_desconocidas(PRODUCE, motivo, ctx.firma)),
            no_hecho=("la regla no aplica a este proyecto: %s" % regla["motivo"],),
        )

    umbral = ctx.invocar(
        "normativa.umbral_de_regla",
        concept_id=CID,
        ambito_id=regla["ambito_id"],
        ejes={
            "numero_salidas": str(ctx.valor(CLAVE_SALIDAS)),
            "condicion": str(ctx.valor(CLAVE_CONDICION)),
        },
    )
    if not umbral.get("ok") or umbral.get("valor") is None:
        motivo = Motivo(
            codigo="umbral_sin_valor",
            detalle=umbral.get("motivo") or umbral.get("detalle", "sin valor aplicable"),
        )
        if umbral.get("pregunta"):
            preguntas.append(umbral["pregunta"])
        return ResultadoDeSkill(
            afirmaciones=tuple(_desconocidas(PRODUCE, motivo, ctx.firma)),
            preguntas=tuple(preguntas),
            no_hecho=("no hay umbral aplicable para los ejes declarados; sin umbral no "
                      "hay comprobación posible y NO se coge un valor parecido",),
        )

    cita = umbral["cita"]
    limite = float(umbral["valor"])
    medida = float(ctx.valor(CLAVE_LONGITUD))

    afirmaciones.append(
        calculo("evacuacion.umbral_m", limite, fuente=ctx.firma, unidad="m", cita=cita)
    )
    afirmaciones.append(
        calculo("evacuacion.holgura_m", round(limite - medida, 3), fuente=ctx.firma,
                unidad="m", cita=cita)
    )
    afirmaciones.append(
        calculo("evacuacion.cumple", medida <= limite, fuente=ctx.firma, cita=cita)
    )

    notas = [
        "Longitud medida: %s m, declarada por el arquitecto. Umbral: %s m, %s."
        % (medida, limite, cita),
    ]
    if umbral.get("pendiente_de_firma_colegiada"):
        no_hecho.append(
            "la regla del corpus está PENDIENTE DE FIRMA COLEGIADA: el resultado es un "
            "ejemplo trabajado, no una comprobación normativa validada"
        )

    return ResultadoDeSkill(
        afirmaciones=tuple(afirmaciones),
        no_hecho=tuple(no_hecho),
        notas=tuple(notas),
    )


def _coherencia_del_veredicto(resultado) -> object:
    """Que `cumple` y `holgura` no se contradigan.

    Puede fallar de verdad: basta con invertir un signo al calcular la holgura,
    que es el error más fácil de cometer y el más difícil de ver leyendo.
    """
    por_nombre = {a.nombre: a for a in resultado.afirmaciones}
    cumple = por_nombre.get("evacuacion.cumple")
    holgura = por_nombre.get("evacuacion.holgura_m")
    if cumple is None or holgura is None or cumple.valor is None or holgura.valor is None:
        return True                       # nada que contrastar: ya está declarado UNKNOWN
    if bool(cumple.valor) != (float(holgura.valor) >= 0):
        return ("«cumple» = %s contradice una holgura de %s m"
                % (cumple.valor, holgura.valor))
    return True


SKILLS = (
    Skill(
        id="revision.recorridos_de_evacuacion",
        version="1.0.0",
        dominio="revision",
        objetivo=(
            "Comprobar si la longitud medida de un recorrido de evacuación respeta el "
            "umbral que el DB-SI fija para esta planta, con la cita del BOE y la "
            "holgura resultante."
        ),
        cuando_usarla=(
            "Cuando se pregunte si un recorrido de evacuación cabe dentro de lo que "
            "permite la norma y la longitud ya esté medida. NO usarla para medir el "
            "recorrido, ni para proponer un trazado alternativo: esta Skill compara, "
            "no diseña."
        ),
        procedimiento=(
            "1. Situar el proyecto territorialmente.",
            "2. Comprobar que la regla de evacuación consta aplicable a este proyecto.",
            "3. Resolver el umbral de la tabla 3.1 para el número de salidas y la "
            "condición declarados, sin replegar a una fila parecida.",
            "4. Restar la longitud medida del umbral y declarar la holgura.",
            "5. Declarar que la regla está pendiente de firma colegiada, si lo está.",
        ),
        requiere=(
            Requisito(clave="territorial.municipio",
                      pregunta="¿En qué municipio está el edificio?"),
            Requisito(clave="proyecto.uso",
                      pregunta="¿Cuál es el uso principal del edificio?"),
            Requisito(clave="proyecto.tipologia",
                      pregunta="¿Qué tipología es?"),
            Requisito(clave=CLAVE_SALIDAS,
                      pregunta="¿La planta tiene una única salida de planta o varias? "
                               "(«una» o «varias»)"),
            Requisito(clave=CLAVE_CONDICION,
                      pregunta="¿Qué condición concurre? («general», «uso_aparcamiento», "
                               "«ocupantes_que_duermen_u_hospitalario_o_escuela», "
                               "«espacio_al_aire_libre_riesgo_irrelevante», "
                               "«salida_directa_exterior_seguro_ocupacion_max_25»)"),
            Requisito(clave=CLAVE_LONGITUD,
                      pregunta="¿Cuántos metros mide el recorrido de evacuación más "
                               "desfavorable hasta la salida de planta?"),
        ),
        capacidades=(
            "territorial.resolver_ambito",
            "normativa.reglas_aplicables",
            "normativa.umbral_de_regla",
        ),
        produce=PRODUCE,
        funcion=_ejecutar,
        verificaciones=(
            Verificacion(
                nombre="coherencia_del_veredicto",
                descripcion="«cumple» y la holgura dicen lo mismo.",
                funcion=_coherencia_del_veredicto,
            ),
            # Un umbral de evacuación fuera de este rango no existe en el DB-SI:
            # si sale, es que se ha leído mal la tabla o se ha colado una unidad.
            valor_dentro_de("evacuacion.umbral_m", minimo=10.0, maximo=200.0),
        ),
        efectos=(),
        limitaciones=(
            "la longitud del recorrido la declara el arquitecto: ArchMuse no la mide",
            "solo comprueba la longitud; no comprueba anchura, sectorización, señalización "
            "ni ocupación",
            "la regla del corpus está pendiente de firma colegiada",
            "no distingue recorridos alternativos ni el más desfavorable entre varios",
        ),
        referencia_normativa="CTE DB-SI 3, apartado 3, tabla 3.1",
    ),
)
