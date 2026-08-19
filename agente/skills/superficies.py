# -*- coding: utf-8 -*-
"""Skill: rellenar el cuadro de superficies de una vivienda (tarea `SK-1`).

PRD aprobado por Pablo el 2026-08-19
(`docs/prd/2026-08-19-skill-del-cuadro-de-superficies.md`), con una condición
textual: **la verificación de la suma es informativa, no bloqueante**, hasta
tener al menos diez proyectos reales con los que calibrar la tolerancia. Aquí
eso es `bloqueante=False` en `_suma_cuadra`, y está escrito para que quien lo
cambie sepa que está cambiando una decisión de producto y no un parámetro.

**Qué añade sobre las capacidades sueltas, que ya hacen las piezas.** Un
arquitecto que rellena un cuadro no encadena funciones: sigue un procedimiento.
Comprueba primero que el plano está en la unidad que dice —porque si no lo
está, todo lo demás sobra—, mide, cruza el resultado contra la superficie útil
que ha medido por otro camino, y no entrega nada sin decir qué ha dejado en
blanco y por qué. Ese orden y esos controles son criterio profesional; el orden
en que un programador llamaría a tres capacidades, no.

**Por qué `ruta_destino` es obligatoria.** Esta Skill *es* el trabajo completo,
y un trabajo completo termina en un fichero que el arquitecto se lleva. Mirar
el cuadro sin tocar nada ya se puede hacer —es la capacidad
`plano.cuadro_de_superficies`, que no tiene efectos y no pide autorización—, y
mezclar las dos cosas en una sola Skill obligaría a autorizar una escritura
para no escribir. Un arquitecto al que se le piden autorizaciones que no hacen
falta aprende a concederlas sin leerlas, y ese día la autorización deja de
servir para nada.

**Lo que esta Skill NO hace,** y va declarado en su manifiesto para que llegue
al acta: no comprueba normativa, no evalúa si las superficies cumplen ningún
mínimo, y no resuelve las ambigüedades del plano — las pregunta.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..afirmacion import Afirmacion, calculo, desconocido
from ..efectos import ESCRIBE_FICHERO
from ..skill import Entregable, ResultadoDeSkill, Skill
from ..verificacion import NoSeHaPodidoComprobar, Verificacion

#: Diferencia relativa admitida entre la suma de las celdas del cuadro y la
#: superficie útil medida sobre la geometría, antes de avisar.
#:
#: **5 % y no otra cifra**, y conviene decir de dónde sale: de ningún sitio
#: todavía. Hay un solo plano real con el que compararla, y elegir un umbral
#: con una muestra de uno es adivinar. Por eso la verificación que la usa es
#: **informativa** —dice la diferencia, no impide entregar— hasta tener diez
#: proyectos. Cuando los haya, esta constante se decide con datos y la
#: verificación puede pasar a bloqueante; hasta entonces, un umbral estricto
#: sólo produciría falsos positivos, y un hallazgo falso destruye la confianza
#: en los verdaderos (`DESTROY_ARCHMUSE.md` §5.1).
TOLERANCIA_SUMA = 0.05

PRODUCE = (
    "plano.escala",
    "plano.superficie_util_total_m2",
    "cuadro.celdas",
    "cuadro.celdas_sin_resolver",
    "cuadro.entregable",
    "cuadro.entregable_pdf",
)


def _sin_hacer(ctx, motivo_codigo: str, detalle: str, pregunta: str,
               ya_hecho: Optional[Dict[str, Any]] = None) -> ResultadoDeSkill:
    """El resultado cuando el procedimiento se corta a mitad.

    Todo lo que la Skill prometía producir y no ha producido sale como
    `UNKNOWN` **con motivo**, nunca ausente: un hueco mudo se lee como «no
    aplica», que es la lectura contraria a la verdadera.
    """
    ya_hecho = ya_hecho or {}
    afirmaciones: List[Afirmacion] = list(ya_hecho.values())
    for clave in PRODUCE:
        if clave in ya_hecho:
            continue
        afirmaciones.append(desconocido(clave, motivo_codigo, detalle, fuente=ctx.firma))
    return ResultadoDeSkill(
        afirmaciones=tuple(afirmaciones),
        preguntas=(pregunta,) if pregunta else (),
        no_hecho=(detalle,),
    )


def _pdf_junto_al(destino_dxf: str) -> str:
    """`plano_relleno.dxf` -> `plano_relleno.pdf`, en la misma carpeta.

    Los dos entregables viajan juntos y con el mismo nombre a propósito: en una
    carpeta con veinte ficheros, que el PDF que explica un DXF se llame igual
    es lo que evita enseñarle a un cliente el acta de otro plano.
    """
    import os.path

    raiz, _ = os.path.splitext(destino_dxf)
    return raiz + ".pdf"


def _ejecutar(ctx) -> ResultadoDeSkill:
    ruta = ctx.argumentos.get("ruta_dxf") or ""
    destino = ctx.argumentos.get("ruta_destino") or ""
    respuestas = ctx.argumentos.get("respuestas") or None
    hechas: Dict[str, Afirmacion] = {}

    # --- 1. ¿Está el plano en la unidad que dice? --------------------------
    # Primero esto y no el cálculo: un plano en milímetros leído como metros
    # cumple todas las superficies mínimas y sale impecable. Si esto falla, lo
    # demás sobra.
    lectura = ctx.invocar("plano.leer_dxf", ruta=ruta)
    if not lectura.get("ok"):
        return _sin_hacer(ctx, lectura.get("error", "plano_ilegible"),
                          lectura.get("detalle", "no se ha podido leer el plano"),
                          lectura.get("pregunta", ""))
    hechas["plano.escala"] = calculo(
        "plano.escala", lectura["escala"].get("unidad"), fuente=ctx.firma,
    )

    # --- 2. La superficie útil, medida por su propio camino ----------------
    # Se mide aparte del cuadro **a propósito**: es la cifra con la que se
    # cruza el resultado en el paso 4. Calcularla del propio cuadro haría que
    # la comprobación comprobara que una suma es igual a sí misma.
    util = ctx.invocar("plano.superficie_util", ruta=ruta)
    medida = None
    if util.get("ok"):
        medidas = [v["valor_m2"] for v in util["viviendas"] if v["valor_m2"] is not None]
        medida = sum(medidas) if medidas else None
    if medida is None:
        hechas["plano.superficie_util_total_m2"] = desconocido(
            "plano.superficie_util_total_m2", "superficie_no_medible",
            "la geometría no permite medir la superficie útil con seguridad",
            fuente=ctx.firma)
    else:
        hechas["plano.superficie_util_total_m2"] = calculo(
            "plano.superficie_util_total_m2", round(medida, 2), fuente=ctx.firma,
            unidad="m2")

    # --- 3. El cuadro, con lo que el arquitecto haya declarado -------------
    borrador = ctx.invocar("plano.cuadro_de_superficies", ruta=ruta, respuestas=respuestas)
    if not borrador.get("ok"):
        return _sin_hacer(ctx, borrador.get("error", "cuadro_no_calculable"),
                          borrador.get("detalle", ""), borrador.get("pregunta", ""),
                          ya_hecho=hechas)
    hechas["cuadro.celdas"] = calculo("cuadro.celdas", borrador["celdas"], fuente=ctx.firma)
    hechas["cuadro.celdas_sin_resolver"] = calculo(
        "cuadro.celdas_sin_resolver", borrador["celdas_sin_resolver"], fuente=ctx.firma)

    # --- 4. Escribir el entregable ----------------------------------------
    escritura = ctx.invocar("plano.escribir_cuadro", ruta_origen=ruta,
                            ruta_destino=destino, respuestas=respuestas)
    if not escritura.get("ok"):
        return _sin_hacer(ctx, escritura.get("error", "no_se_ha_podido_escribir"),
                          escritura.get("detalle", ""), escritura.get("pregunta", ""),
                          ya_hecho=hechas)
    hechas["cuadro.entregable"] = calculo(
        "cuadro.entregable", escritura["ruta_destino"], fuente=ctx.firma)

    # --- 5. El PDF legible, con el porqué de cada celda -------------------
    # El DXF lleva los números y vuelve al proyecto; el PDF es lo que el
    # arquitecto lee para decidir si se fía, y lo que puede enseñar seis meses
    # después. Si falla, NO se pierde el DXF que ya está escrito: se declara
    # con motivo y el trabajo principal sigue entregado.
    ruta_pdf = _pdf_junto_al(destino)
    pdf = ctx.invocar("plano.cuadro_en_pdf", ruta=ruta, ruta_destino=ruta_pdf,
                      respuestas=respuestas)
    if pdf.get("ok"):
        hechas["cuadro.entregable_pdf"] = calculo(
            "cuadro.entregable_pdf", pdf["ruta_destino"], fuente=ctx.firma)
    else:
        hechas["cuadro.entregable_pdf"] = desconocido(
            "cuadro.entregable_pdf", pdf.get("error", "pdf_no_escrito"),
            pdf.get("detalle", "no se ha podido escribir el PDF del cuadro"),
            fuente=ctx.firma)

    preguntas = tuple(p["titulo"] for p in borrador.get("preguntas_pendientes") or ())
    no_hecho = tuple(
        "«%s»: %s" % (c["campo"], c["motivo"] or "sin motivo declarado")
        for c in escritura.get("celdas_sin_resolver") or ()
    )
    notas = [
        "El DXF original conserva su sha256 (%s): no se ha tocado."
        % escritura["sello_origen_sha256"][:12],
    ]
    if borrador.get("celdas_declaradas_por_el_arquitecto"):
        notas.append(
            "Declarado por el arquitecto, no calculado por ArchMuse: %s."
            % ", ".join(borrador["celdas_declaradas_por_el_arquitecto"]))

    return ResultadoDeSkill(
        afirmaciones=tuple(hechas.values()),
        entregables=tuple(
            e for e in (
                Entregable(nombre="Cuadro de superficies relleno", tipo="dxf",
                           ruta=escritura["ruta_destino"],
                           sello=escritura.get("sello_destino_sha256")),
                (Entregable(nombre="Cuadro de superficies explicado", tipo="pdf",
                            ruta=pdf["ruta_destino"],
                            sello=pdf.get("sello_destino_sha256"))
                 if pdf.get("ok") else None),
            ) if e is not None
        ),
        preguntas=preguntas,
        no_hecho=no_hecho,
        notas=tuple(notas),
    )


# --- Las verificaciones -----------------------------------------------------

def _valor(resultado, nombre):
    for a in resultado.afirmaciones:
        if a.nombre == nombre:
            return a.valor
    return None


def _suma_cuadra(resultado) -> Any:
    """La comprobación que hace un arquitecto y que ninguna capacidad hace.

    Cruza la suma de las celdas calculadas del cuadro contra la superficie útil
    medida sobre la geometría por otro camino. Si difieren mucho, o falta una
    pieza del cuadro o sobra una del plano — y en los dos casos hay que mirarlo
    antes de firmar.

    **Es informativa, no bloqueante,** por decisión de Pablo del 2026-08-19: la
    tolerancia no está calibrada (ver `TOLERANCIA_SUMA`) y un hallazgo falso
    destruye la confianza en los verdaderos. Dice la diferencia; no impide
    entregar.
    """
    celdas = _valor(resultado, "cuadro.celdas")
    medida = _valor(resultado, "plano.superficie_util_total_m2")
    if not resultado.entregables and not celdas:
        return True          # el procedimiento se cortó antes: no hay qué cruzar
    # El primer plano real cayó aquí: su geometría tiene recintos solapados, así
    # que `plano.superficie_util` se negó —bien— a publicar un total, y no hay
    # contra qué cruzar. Eso NO es que la suma no cuadre: es que no se ha podido
    # mirar, y decirlo como un fallo acusaría al plano de un defecto que nadie
    # ha comprobado. De ahí el tercer estado.
    if not celdas:
        return NoSeHaPodidoComprobar(
            "no hay cuadro que sumar: el cálculo del cuadro no llegó a producir celdas"
        )
    if medida in (None, 0):
        return NoSeHaPodidoComprobar(
            "no hay superficie útil medida contra la que cruzar la suma. La suma del "
            "cuadro puede estar bien o mal: no se ha comprobado. El motivo por el que "
            "no se pudo medir va declarado junto a «plano.superficie_util_total_m2»."
        )

    total = 0.0
    contadas = 0
    for celda in celdas:
        texto = (celda.get("texto") or "").replace("m²", "").replace(",", ".").strip()
        if celda.get("estado") not in ("CALCULADO", "CERO_REAL"):
            continue
        if "total" in celda.get("campo", ""):
            continue          # sumar un total sería contar dos veces
        try:
            total += float(texto)
            contadas += 1
        except ValueError:
            continue          # no es una superficie (p. ej. «VT1 /3»): no se suma
    if not contadas:
        return NoSeHaPodidoComprobar(
            "ninguna celda del cuadro tiene una superficie que sumar"
        )

    diferencia = abs(total - float(medida)) / float(medida)
    if diferencia <= TOLERANCIA_SUMA:
        return True
    return ("la suma de las celdas (%.2f m²) difiere un %.1f %% de la superficie útil "
            "medida sobre la geometría (%.2f m²). O falta una pieza en el cuadro, o "
            "sobra una en el plano: conviene mirarlo antes de firmar."
            % (total, diferencia * 100, float(medida)))


def _nada_sin_resolver_lleva_un_numero(resultado) -> Any:
    """La tercera condición de la aprobación de `TL-2`, comprobada aquí también.

    La capacidad ya lo garantiza; esto lo vuelve a mirar sobre el resultado
    entregado, que es lo que se guarda en el acta. Dos comprobaciones del mismo
    invariante en capas distintas no es redundancia: es lo que hace que quitar
    una no lo desactive.
    """
    for celda in _valor(resultado, "cuadro.celdas") or ():
        if celda.get("estado") in ("NO_DISPONIBLE", "BLOQUEADO"):
            texto = (celda.get("texto") or "").replace("m²", "").replace(",", ".").strip()
            try:
                float(texto)
            except ValueError:
                continue
            return ("la celda «%s» está sin resolver y lleva el número %s: eso es "
                    "exactamente lo que no puede pasar" % (celda.get("campo"), texto))
    return True


def _el_original_no_se_ha_tocado(resultado) -> Any:
    """Sin esto, la nota del acta sería una frase y no una comprobación.

    **Cuando no hay entregable no hay nada que acreditar**, y eso pasa: el
    procedimiento se corta a mitad porque el DXF no traía cuadro, o porque
    faltaba un dato. Exigir el sello ahí convertiría una respuesta legítima
    —«no he podido, esto es lo que falta»— en un resultado no verificado, y el
    arquitecto leería un fallo del sistema donde sólo hay una pregunta.
    """
    if not resultado.entregables:
        return True
    for nota in resultado.notas:
        if "conserva su sha256" in nota:
            return True
    return ("se ha entregado un fichero y el resultado no acredita que el DXF "
            "original siga intacto")


SKILLS = (
    Skill(
        id="superficies.cuadro_de_vivienda",
        version="1.0.0",
        dominio="superficies",
        objetivo=(
            "Rellenar el cuadro de superficies de una vivienda a partir de su DXF y "
            "entregar una copia del plano con el cuadro completado, diciendo celda a "
            "celda de dónde sale cada número y qué no se ha podido calcular."
        ),
        cuando_usarla=(
            "Cuando el objetivo sea el entregable: «rellena el cuadro de superficies de "
            "este plano», «complétame la tabla de superficies». NO usarla sólo para "
            "mirar el cuadro sin tocar nada —para eso está la capacidad "
            "plano.cuadro_de_superficies, que no escribe ni pide autorización— ni para "
            "comprobar si las superficies cumplen normativa, que esta Skill no hace."
        ),
        procedimiento=(
            "1. Comprobar que el plano está en la unidad que declara. Si no se puede "
            "saber, PARAR y preguntar: un plano en milímetros leído como metros cumple "
            "todos los mínimos y sale impecable.",
            "2. Medir la superficie útil sobre la geometría, por su propio camino.",
            "3. Calcular el cuadro celda a celda, incorporando lo que el arquitecto "
            "haya declarado y marcándolo como suyo.",
            "4. Cruzar la suma de las celdas contra la superficie medida en el paso 2 "
            "y avisar si no cuadran (aviso, no bloqueo: la tolerancia aún no está "
            "calibrada).",
            "5. Escribir una COPIA del DXF con el cuadro relleno. El original no se "
            "toca, y su sha256 se verifica antes y después.",
            "6. Escribir el PDF que explica el cuadro celda a celda: de dónde sale "
            "cada número y por qué las demás están en blanco.",
            "7. Declarar qué celdas han quedado sin resolver y por qué, y qué preguntas "
            "las desbloquearían.",
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta_dxf": {"type": "string",
                             "description": "El DXF del arquitecto. Sólo se lee."},
                "ruta_destino": {"type": "string",
                                 "description": ("Dónde se escribe la copia rellena. No "
                                                 "puede ser el origen ni un fichero que "
                                                 "ya exista.")},
                "respuestas": {
                    "type": ["array", "null"],
                    "description": ("Lo que el arquitecto declara para las celdas que no "
                                    "se pueden calcular del plano."),
                    "items": {"type": "object"},
                },
            },
            "required": ["ruta_dxf", "ruta_destino"],
            "additionalProperties": False,
        },
        # Nada del proyecto: el plano viene en la petición, no de la memoria.
        # Cuando exista el grafo portante, la escala y la capa confirmadas una
        # vez vivirán ahí y dejarán de preguntarse en cada ejecución.
        requiere=(),
        capacidades=("plano.leer_dxf", "plano.superficie_util",
                     "plano.cuadro_de_superficies", "plano.escribir_cuadro",
                     "plano.cuadro_en_pdf"),
        produce=PRODUCE,
        funcion=_ejecutar,
        verificaciones=(
            Verificacion(
                nombre="nada_sin_resolver_lleva_un_numero",
                descripcion=("Una celda que no se ha podido calcular no puede salir con "
                             "una cifra."),
                funcion=_nada_sin_resolver_lleva_un_numero,
            ),
            Verificacion(
                nombre="el_original_no_se_ha_tocado",
                descripcion="El DXF de entrada conserva su sha256.",
                funcion=_el_original_no_se_ha_tocado,
            ),
            Verificacion(
                nombre="la_suma_cuadra_con_la_superficie_medida",
                descripcion=("La suma de las celdas del cuadro concuerda con la "
                             "superficie útil medida sobre la geometría."),
                funcion=_suma_cuadra,
                # INFORMATIVA por decisión de Pablo (2026-08-19): la tolerancia
                # no está calibrada. Cambiar esto a True es una decisión de
                # producto, no un ajuste — ver `TOLERANCIA_SUMA`.
                bloqueante=False,
            ),
        ),
        efectos=(ESCRIBE_FICHERO,),
        limitaciones=(
            "no comprueba normativa: rellena el cuadro, no dice si el proyecto cumple",
            "no evalúa si las superficies respetan ningún mínimo",
            "no resuelve las ambigüedades del plano: las pregunta",
            "la tolerancia de la comprobación de la suma no está calibrada; el aviso es "
            "informativo y no impide la entrega",
            "sólo admite un DXF con una única vivienda detectada",
        ),
    ),
)
