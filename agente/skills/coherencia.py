# -*- coding: utf-8 -*-
"""Skill: revisar un plano antes de entregarlo (tarea `CO-5`).

PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`.

**Qué añade sobre la capacidad suelta.** La capacidad `plano.coherencia` mira y
devuelve una lista. Un arquitecto que repasa un plano antes de entregarlo hace
otra cosa: comprueba **primero** que el plano está en la unidad que dice —porque
un plano en milímetros leído como metros da solapes de cuatro millones de metros
cuadrados presentados con toda seriedad—, mira, y **entrega un documento** que
dice qué ha mirado, no sólo qué ha encontrado. Ese orden y ese cierre son el
procedimiento; encadenar dos funciones, no.

**Por qué esta Skill no está bloqueada por `D-7`,** que es la pregunta que hay
que hacerse antes de escribir cualquier Skill nueva. `agente/skills/__init__.py`
deja claro que las Skills que emitan criterio profesional esperan a que se
decida quién valida su procedimiento. Ésta **no emite criterio**: no dice que un
hallazgo sea grave, ni urgente, ni que el plano esté mal. Dice «estas dos piezas
se solapan 4,00 m²» y quién es cada una, que es un hecho que el arquitecto puede
ir a comprobar en tres clics. La frontera está en la verificación
`ningun_hallazgo_lleva_gravedad`, que es bloqueante: cruzarla no es un cambio de
formato, es cambiar de producto.

**Lo que esta Skill NO hace,** y va en su manifiesto para que llegue al acta: no
comprueba normativa, no dice si el proyecto cumple, no ordena los hallazgos por
importancia, y no toca el DXF del arquitecto — lo abre para leer y comprueba su
sha256 antes y después.
"""
from __future__ import annotations

from typing import Any, Dict

from ..afirmacion import Afirmacion, calculo
from ..efectos import ESCRIBE_FICHERO
from ..skill import Entregable, ResultadoDeSkill, Skill
from ..verificacion import Verificacion
from ._comun import sin_producir, valor

#: Palabras que graduarían la gravedad de un hallazgo. Si alguna aparece en el
#: vocabulario de salida, la Skill ha dejado de decir qué mide y ha empezado a
#: opinar — que es criterio profesional, y el de ArchMuse está sin firmar
#: (`D-7`). La lista es corta a propósito: no es un filtro de contenido, es un
#: detector de que alguien ha cruzado la frontera sin darse cuenta.
PALABRAS_DE_GRAVEDAD = (
    "grave", "leve", "crítico", "critico", "urgente", "prioridad", "severidad",
    "importante", "menor ", "gravedad",
)

PRODUCE = (
    "revision.recintos",
    "revision.hallazgos",
    "revision.recuento_por_tipo",
    "revision.comprobado",
    "revision.informe",
    # `docs/prd/2026-08-21-ubicacion-hallazgos-visor2d.md` (UB-6, R-1): sin
    # esta entrada, `recintos_geometria` existe en `Revision.a_dict()` pero
    # muere aquí -- `agente/acta.py:levantar()` sólo copia lo que llegue como
    # `Afirmacion`, no reconstruye nada a partir del dict crudo de la
    # capacidad. Mismo patrón que las 5 entradas de arriba, no uno nuevo.
    "revision.recintos_geometria",
)


def _sin_hacer(ctx, codigo: str, detalle: str, pregunta: str) -> ResultadoDeSkill:
    """El procedimiento se corta: todo lo prometido sale `UNKNOWN` con motivo.

    Cortarse a mitad **no es un fallo del sistema**: es una respuesta con su
    pregunta. Un plano cuya unidad no se puede deducir no produce un informe
    malo — no produce informe, y dice qué hay que contestar para que lo haya.
    """
    return ResultadoDeSkill(
        afirmaciones=sin_producir(PRODUCE, codigo=codigo, detalle=detalle,
                                  fuente=ctx.firma),
        preguntas=(pregunta,) if pregunta else (),
        no_hecho=(detalle,),
    )


def _ejecutar(ctx) -> ResultadoDeSkill:
    ruta = ctx.argumentos.get("ruta_dxf") or ""
    destino = ctx.argumentos.get("ruta_informe") or ""
    capa = ctx.argumentos.get("capa")
    factor = ctx.argumentos.get("factor_escala")

    # --- 1. ¿Está el plano en la unidad que dice? --------------------------
    # Lo primero, igual que en el cuadro de superficies y por el mismo motivo:
    # medir un solape sin saber la unidad produce una cifra de siete dígitos
    # que se lee como un hallazgo enorme y no significa nada.
    revision = ctx.invocar("plano.coherencia", ruta=ruta, capa=capa,
                           factor_escala=factor)
    if not revision.get("ok"):
        return _sin_hacer(ctx, revision.get("error", "plano_ilegible"),
                          revision.get("detalle", "no se ha podido leer el plano"),
                          revision.get("pregunta", ""))

    hechas: Dict[str, Afirmacion] = {
        "revision.recintos": calculo("revision.recintos", revision.get("recintos", 0),
                                     fuente=ctx.firma),
        "revision.hallazgos": calculo("revision.hallazgos",
                                      revision.get("hallazgos") or [], fuente=ctx.firma),
        "revision.recuento_por_tipo": calculo(
            "revision.recuento_por_tipo", revision.get("recuento_por_tipo") or {},
            fuente=ctx.firma),
        "revision.comprobado": calculo("revision.comprobado",
                                       revision.get("comprobado") or [], fuente=ctx.firma),
        "revision.recintos_geometria": calculo(
            "revision.recintos_geometria", revision.get("recintos_geometria") or [],
            fuente=ctx.firma),
    }

    # --- 2. El documento que el arquitecto se lleva ------------------------
    # plano.informe_de_coherencia se fusionó en plano.entregable_en_pdf
    # (Prompt 1.7, cierre de C4, 2026-08-21) — mismo comportamiento, tipo="coherencia".
    escritura = ctx.invocar("plano.entregable_en_pdf", tipo="coherencia", ruta=ruta,
                            ruta_destino=destino, capa=capa, factor_escala=factor)
    if not escritura.get("ok", True) or not escritura.get("ruta_destino"):
        return ResultadoDeSkill(
            afirmaciones=sin_producir(
                PRODUCE, codigo=escritura.get("error", "informe_no_escrito"),
                detalle=escritura.get("detalle", "no se ha podido escribir el informe"),
                fuente=ctx.firma, ya_hecho=hechas),
            preguntas=(escritura["pregunta"],) if escritura.get("pregunta") else (),
            no_hecho=(escritura.get("detalle", "no se ha podido escribir el informe"),),
        )
    hechas["revision.informe"] = calculo("revision.informe",
                                         escritura["ruta_destino"], fuente=ctx.firma)

    hallazgos = revision.get("hallazgos") or []
    notas = [
        "El DXF original conserva su sha256 (%s): no se ha tocado."
        % (escritura.get("sello_origen_sha256") or "")[:12],
    ]
    if hallazgos:
        notas.append(
            "%d hallazgo(s), sin ordenar por importancia: ArchMuse mide, el criterio "
            "lo pone el arquitecto." % len(hallazgos))
    else:
        notas.append(
            "No se ha encontrado nada. El informe enumera qué se ha comprobado, que es "
            "lo que hace que «nada» signifique algo.")

    return ResultadoDeSkill(
        afirmaciones=tuple(hechas.values()),
        entregables=(
            Entregable(nombre="Revisión de coherencia del plano", tipo="pdf",
                       ruta=escritura["ruta_destino"],
                       sello=escritura.get("sello_destino_sha256")),
        ),
        no_hecho=tuple(revision.get("no_comprobado") or ()),
        notas=tuple(notas),
    )


# --- Las verificaciones -----------------------------------------------------

def _ningun_hallazgo_sin_entidad(resultado) -> Any:
    """Un hallazgo que no se puede ir a comprobar gasta tiempo en vez de ahorrarlo.

    `analyzer/coherencia.py` ya lo impide al construir el `Hallazgo`. Esto lo
    vuelve a mirar sobre lo que se ha entregado, que es lo que queda en el acta.
    Dos comprobaciones del mismo invariante en capas distintas no es redundancia:
    es lo que hace que quitar una no lo desactive.
    """
    for h in valor(resultado, "revision.hallazgos") or ():
        if not (h.get("entidad") or "").strip():
            return ("el hallazgo «%s» no dice dónde mirarlo, y un aviso que no se "
                    "puede localizar no sirve" % h.get("tipo"))
    return True


def _ningun_hallazgo_lleva_gravedad(resultado) -> Any:
    """La frontera con el criterio profesional, comprobada y no prometida.

    Decir «esto es grave» es criterio de arquitecto, y el de ArchMuse está sin
    firmar (`D-7`). Mientras esta verificación pase, esta Skill mide; el día que
    alguien la haga fallar, ArchMuse ha empezado a opinar sobre el trabajo de un
    colegiado y eso es una decisión de producto, no un ajuste de formato.
    """
    for h in valor(resultado, "revision.hallazgos") or ():
        if "severidad" in h or "gravedad" in h or "prioridad" in h:
            return ("el hallazgo «%s» lleva un campo de gravedad: esta Skill mide, "
                    "no califica" % h.get("tipo"))
        texto = ("%s %s" % (h.get("tipo", ""), h.get("descripcion", ""))).lower()
        for palabra in PALABRAS_DE_GRAVEDAD:
            if palabra in texto:
                return ("el hallazgo «%s» califica la gravedad («%s»): esta Skill dice "
                        "qué es y cuánto mide, y el criterio lo pone el arquitecto"
                        % (h.get("tipo"), palabra.strip()))
    return True


def _el_original_no_se_ha_tocado(resultado) -> Any:
    """Sin esto, la nota del acta sería una frase y no una comprobación."""
    if not resultado.entregables:
        return True
    for nota in resultado.notas:
        if "conserva su sha256" in nota:
            return True
    return ("se ha entregado un informe y el resultado no acredita que el DXF "
            "original siga intacto")


def _un_informe_sin_hallazgos_dice_que_ha_mirado(resultado) -> Any:
    """Un informe vacío se lee como «no ha funcionado», y además afirmaría más
    de lo que este documento puede sostener."""
    if valor(resultado, "revision.hallazgos"):
        return True
    if valor(resultado, "revision.informe") and not valor(resultado, "revision.comprobado"):
        return ("se entrega un informe sin hallazgos y sin decir qué se ha comprobado: "
                "así «no se ha encontrado nada» no significa nada")
    return True


SKILLS = (
    Skill(
        id="revision.coherencia_del_plano",
        version="1.0.0",
        dominio="revision",
        objetivo=(
            "Revisar si un DXF es coherente consigo mismo antes de entregarlo —recintos "
            "solapados, contornos cerrados por suposición, rótulos repetidos o ausentes, "
            "y si el cuadro de superficies y el dibujo nombran y cuentan las mismas "
            "piezas— y entregar el informe con la entidad y la magnitud de cada hallazgo."
        ),
        cuando_usarla=(
            "Cuando el objetivo sea repasar un plano antes de que salga del estudio, o "
            "entender qué hay dentro de un DXF que ha dibujado otro. NO usarla para "
            "comprobar normativa —esta Skill no mira ninguna norma— ni para rellenar el "
            "cuadro de superficies, que es superficies.cuadro_de_vivienda. Para mirar sin "
            "generar ningún documento está la capacidad plano.coherencia, que no escribe "
            "ni pide autorización."
        ),
        procedimiento=(
            "1. Leer el plano comprobando la unidad en la que está dibujado. Si no se "
            "puede saber, PARAR y preguntar: medir un solape sin saber la unidad da una "
            "cifra de siete dígitos que parece un hallazgo enorme y no significa nada.",
            "2. Buscar recintos que se solapen: son metros contados dos veces, y explican "
            "por qué después no cuadra ninguna suma.",
            "3. Recoger los contornos que el fichero declara abiertos y se han cerrado "
            "por suposición, y la geometría que no ha entrado en el análisis, con su "
            "motivo. Un descarte silencioso es una superficie que falta sin que nadie lo "
            "sepa.",
            "4. Mirar los rótulos: los que faltan y los que se repiten. Un rótulo "
            "repetido no es un error, pero impide repartir sin preguntar.",
            "5. Contrastar el cuadro de superficies contra el dibujo, por familia y por "
            "recuento. Se dice como discrepancia, NO como defecto: un pasillo puede no "
            "dibujarse como recinto propio.",
            "6. Escribir el informe con cada hallazgo, su entidad y su magnitud, SIN "
            "ordenarlos por importancia y SIN calificar su gravedad.",
            "7. Declarar qué se ha comprobado y qué no se ha podido comprobar y por qué, "
            "también cuando no se ha encontrado nada.",
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta_dxf": {"type": "string",
                             "description": "El DXF del arquitecto. Sólo se lee."},
                "ruta_informe": {"type": "string",
                                 "description": ("Dónde se escribe el informe PDF. No "
                                                 "puede ser el propio plano.")},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de recintos, si ya está confirmada."},
                "factor_escala": {"type": ["number", "null"],
                                  "description": "Multiplicador a metros, si ya está "
                                                 "confirmado."},
            },
            "required": ["ruta_dxf", "ruta_informe"],
            "additionalProperties": False,
        },
        # Nada del proyecto: el plano viene en la petición, no de la memoria. Es
        # justamente lo que hace que esta Skill sirva para un DXF ajeno, que es
        # su caso de más valor.
        requiere=(),
        capacidades=("plano.coherencia", "plano.entregable_en_pdf"),
        produce=PRODUCE,
        funcion=_ejecutar,
        verificaciones=(
            Verificacion(
                nombre="ningun_hallazgo_sin_entidad",
                descripcion="Todo hallazgo dice dónde se puede ir a comprobar.",
                funcion=_ningun_hallazgo_sin_entidad,
            ),
            Verificacion(
                nombre="ningun_hallazgo_lleva_gravedad",
                descripcion=("Ningún hallazgo califica su gravedad: la Skill mide, el "
                             "criterio lo pone el arquitecto."),
                funcion=_ningun_hallazgo_lleva_gravedad,
            ),
            Verificacion(
                nombre="el_original_no_se_ha_tocado",
                descripcion="El DXF de entrada conserva su sha256.",
                funcion=_el_original_no_se_ha_tocado,
            ),
            Verificacion(
                nombre="un_informe_sin_hallazgos_dice_que_ha_mirado",
                descripcion=("Un informe limpio enumera lo comprobado, para que «nada» "
                             "signifique algo."),
                funcion=_un_informe_sin_hallazgos_dice_que_ha_mirado,
            ),
        ),
        efectos=(ESCRIBE_FICHERO,),
        limitaciones=(
            "no comprueba normativa: dice si el plano es coherente consigo mismo, no si "
            "el proyecto cumple",
            "no gradúa ni ordena los hallazgos por importancia: eso es criterio "
            "profesional y lo pone el arquitecto",
            "una discrepancia entre el cuadro y el dibujo no es necesariamente un error: "
            "un pasillo puede no dibujarse como recinto propio",
            "no lee muros, huecos ni carpintería: sólo los recintos de la capa de áreas",
            "no compara la cifra escrita en una celda del cuadro contra la medida: hoy no "
            "hay ningún plano real con el cuadro relleno con el que comprobar que eso "
            "funciona",
            "sólo admite un DXF con una única vivienda detectada",
        ),
    ),
)
