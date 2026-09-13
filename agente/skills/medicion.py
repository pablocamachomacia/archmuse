# -*- coding: utf-8 -*-
"""Skill: medir las superficies útiles de una planta con varias viviendas.

**El trabajo que esto hace, en la frase de un arquitecto:** «mídeme esta planta
y dime la superficie de cada vivienda, pieza a pieza». Es el trabajo previo a
todo lo demás —la memoria, la ficha comercial, el cuadro que hay que dibujar, la
comprobación de superficies mínimas— y hoy se hace a mano, recinto a recinto,
con una calculadora y volviendo a empezar en cada revisión del plano.

**Por qué es una Skill y no una capacidad suelta.** La capacidad
`plano.medicion_de_la_planta` mide y devuelve una lista. Un arquitecto que mide
una planta hace tres cosas más, y en este orden: comprueba **primero** en qué
unidad está dibujado el plano —porque un plano en milímetros leído como metros
da viviendas de sesenta millones de metros cuadrados presentadas con toda
seriedad—, **se niega a totalizar** lo que no cuadra en vez de dar la suma
igualmente, y **entrega un documento** que dice de dónde sale cada cifra. Ese
orden y ese cierre son el procedimiento.

**En qué se diferencia de `superficies.cuadro_de_vivienda`, que es la pregunta
que decide cuál elegir.** Aquélla rellena **el cuadro que el plano ya trae
dibujado**, escribiendo en una copia del DXF: es la buena cuando el plano trae
su `ACAD_TABLE`, porque devolver el plano del arquitecto con su propia tabla
rellena vale más que darle una lista. Ésta no necesita que exista ninguna tabla
y no se rinde ante una planta con varias viviendas, que es el caso normal. Las
dos miden igual; lo que cambia es qué se entrega.

**Por qué esta Skill no está bloqueada por `D-7`.** No emite criterio
profesional: no dice si una vivienda es pequeña, ni si un solape es un error del
plano o una convención de su autor, ni ordena nada por importancia. Dice qué
piezas hay, cuánto miden, de dónde sale cada cifra y qué impide totalizar. La
frontera está en la verificación bloqueante `la_medicion_no_califica`, igual que
en la revisión de coherencia: cruzarla no es un cambio de formato, es cambiar de
producto.

**Lo que NO hace,** y va en el manifiesto para que llegue al acta: no mide
superficie construida, no comprueba normativa ni ningún mínimo, no rellena el
cuadro del DXF y no toca el plano del arquitecto.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..afirmacion import Afirmacion, calculo, desconocido
from ..efectos import ESCRIBE_FICHERO
from ..skill import Entregable, ResultadoDeSkill, Skill
from ..verificacion import Verificacion
from ._comun import sin_producir, valor
from .coherencia import PALABRAS_DE_GRAVEDAD

PRODUCE = (
    "medicion.viviendas",
    "medicion.piezas",
    "medicion.viviendas_con_total",
    "medicion.sin_total",
    #: Superficie útil de la PLANTA entera, **en dos hechos separados que nadie
    #: debe sumar** (criterio del arquitecto, 2026-09-07). Los calcula
    #: `analyzer/medicion.py` (`Medicion.util_interior_m2` / `util_exterior_m2`),
    #: que es donde vive la regla; aquí sólo se publican como hechos con su
    #: procedencia. Una cifra calculada en la capa de presentación sería una
    #: cifra sin tool detrás, y eso es la regla de oro del §1 de
    #: `ARCHMUSE_SPEC.md`. **Y sumar estos dos hechos en el consumidor sería
    #: reconstruir a mano el `medicion.total_util_m2` que se ha retirado.**
    "medicion.util_interior_m2",
    "medicion.util_exterior_m2",
    #: Lo que NO impide el total de la planta pero se lee pegado a él: un
    #: rótulo «VT…» sin ningún recinto asignado. Hecho aparte y no una nota al
    #: pie porque es la cifra del total la que podría estar corta, y el aviso
    #: tiene que poder viajar hasta donde viaje la cifra.
    "medicion.advertencias_del_total",
    "medicion.informe",
)


def _sin_hacer(ctx, codigo: str, detalle: str, pregunta: str,
               ya_hecho=None) -> ResultadoDeSkill:
    """El procedimiento se corta: todo lo prometido sale `UNKNOWN` con motivo.

    Cortarse no es un fallo del sistema. Un plano cuya unidad no se puede
    deducir no produce una medición mala: no produce medición, y dice qué hay
    que contestar para que la haya.
    """
    return ResultadoDeSkill(
        afirmaciones=sin_producir(PRODUCE, codigo=codigo, detalle=detalle,
                                  fuente=ctx.firma, ya_hecho=ya_hecho),
        preguntas=(pregunta,) if pregunta else (),
        no_hecho=(detalle,),
    )


def _sin_total(viviendas) -> List[Dict[str, Any]]:
    """Qué viviendas no llevan total y por qué. Derivado, no redactado."""
    return [
        {"vivienda": v.get("vivienda"), "impedimentos": list(v.get("impedimentos") or ())}
        for v in viviendas
        if v.get("util_interior_m2") is None
    ]


def _hecho_de_superficie(medicion: Dict[str, Any], campo: str, firma: str) -> Afirmacion:
    """Una de las dos superficies de la planta como hecho: la cifra, o UNKNOWN
    con su motivo.

    Las dos ramas salen de `analyzer/medicion.py`; aquí no se decide nada. Una
    cifra ausente y sin motivo es indistinguible de un fallo del programa, así
    que el `desconocido` lleva siempre el impedimento que lo explica.
    """
    valor_m2 = medicion.get(campo)
    if valor_m2 is None:
        motivos = medicion.get("impedimentos_del_total") or ()
        return desconocido(
            "medicion.%s" % campo, "planta_no_totalizable",
            "; ".join(motivos) or "la planta no se ha podido totalizar",
            fuente=firma)
    return calculo("medicion.%s" % campo, valor_m2, fuente=firma, unidad="m2")


def _ejecutar(ctx) -> ResultadoDeSkill:
    ruta = ctx.argumentos.get("ruta_dxf") or ""
    destino = ctx.argumentos.get("ruta_informe") or ""
    capa = ctx.argumentos.get("capa")
    factor = ctx.argumentos.get("factor_escala")
    # **Una peticion del arquitecto que viaja hasta el parser.** No se pone a
    # `True` por defecto en ningun punto del camino: si no llega, no se alinea.
    alinear = ctx.argumentos.get("alinear_rotulos") is True

    # --- 1. Medir, sin tocar nada -----------------------------------------
    # Lo primero y sin efectos, para que un plano ilegible se detecte antes de
    # que exista ningún fichero de salida a medio escribir.
    medicion = ctx.invocar("plano.medicion_de_la_planta", ruta=ruta, capa=capa,
                           factor_escala=factor, alinear_rotulos=alinear)
    if not medicion.get("ok"):
        return _sin_hacer(ctx, medicion.get("error", "plano_ilegible"),
                          medicion.get("detalle", "no se ha podido leer el plano"),
                          medicion.get("pregunta", ""))

    viviendas = medicion.get("viviendas") or []
    hechas: Dict[str, Afirmacion] = {
        "medicion.viviendas": calculo("medicion.viviendas", viviendas, fuente=ctx.firma),
        "medicion.piezas": calculo("medicion.piezas", medicion.get("piezas", 0),
                                   fuente=ctx.firma),
        "medicion.viviendas_con_total": calculo(
            "medicion.viviendas_con_total", medicion.get("viviendas_con_total", 0),
            fuente=ctx.firma),
        "medicion.sin_total": calculo("medicion.sin_total", _sin_total(viviendas),
                                      fuente=ctx.firma),
        "medicion.util_interior_m2": _hecho_de_superficie(
            medicion, "util_interior_m2", ctx.firma),
        "medicion.util_exterior_m2": _hecho_de_superficie(
            medicion, "util_exterior_m2", ctx.firma),
        "medicion.advertencias_del_total": calculo(
            "medicion.advertencias_del_total",
            list(medicion.get("advertencias_del_total") or ()), fuente=ctx.firma),
        # `C-10`: los contornos que ArchMuse ha tenido que reparar para poder
        # medirlos. **Se declara como afirmación y no como un campo suelto**
        # porque es exactamente eso: algo que el sistema afirma haber hecho con
        # el dibujo del arquitecto, y que tiene que poder rastrearse hasta quién
        # lo hizo. Una reparación callada es peor que un descarte callado: el
        # número sale bien, el cuadro se rellena, y nadie va a mirar por qué.
        "medicion.geometria_reparada": calculo(
            "medicion.geometria_reparada",
            list(medicion.get("geometria_reparada") or ()), fuente=ctx.firma),
        # **La correccion de rotulos que se ha aplicado, si alguna.** Es
        # afirmacion y no campo suelto por la regla de oro del proyecto: esta
        # medicion DEPENDE de un desplazamiento que ArchMuse ha aplicado, y una
        # cifra que se apoya en algo que no consta es una cifra sin procedencia.
        "medicion.rotulos_alineados": calculo(
            "medicion.rotulos_alineados", medicion.get("rotulos_alineados"),
            fuente=ctx.firma),
        "medicion.rotulos_desplazados": calculo(
            "medicion.rotulos_desplazados", medicion.get("rotulos_desplazados"),
            fuente=ctx.firma),
        "medicion.capa_de_rotulos": calculo(
            "medicion.capa_de_rotulos", medicion.get("capa_de_rotulos"),
            fuente=ctx.firma),
    }

    if not viviendas:
        return _sin_hacer(
            ctx, "ninguna_vivienda",
            "No se ha podido separar ninguna vivienda en «%s»: el plano no tiene "
            "recintos legibles en la capa de áreas." % ruta,
            "¿Es ésta la capa donde están dibujados los recintos, o hay otra?",
            ya_hecho=hechas)

    # --- 2. El documento que el arquitecto se lleva ------------------------
    # La lista de «lo que NO se comprueba» la deriva la propia capacidad de los
    # manifiestos, y por eso no se le pasa desde aquí: si la Skill pudiera
    # dictarla, podría entregar un documento con la lista recortada.
    # plano.medicion_en_pdf se fusionó en plano.entregable_en_pdf (Prompt 1.7,
    # cierre de C4, 2026-08-21) — mismo comportamiento, tipo="medicion".
    escritura = ctx.invocar("plano.entregable_en_pdf", tipo="medicion", ruta=ruta,
                            ruta_destino=destino, capa=capa, factor_escala=factor)
    if not escritura.get("ok", True) or not escritura.get("ruta_destino"):
        detalle = escritura.get("detalle", "no se ha podido escribir la medición")
        return ResultadoDeSkill(
            afirmaciones=sin_producir(
                PRODUCE, codigo=escritura.get("error", "informe_no_escrito"),
                detalle=detalle, fuente=ctx.firma, ya_hecho=hechas),
            preguntas=(escritura["pregunta"],) if escritura.get("pregunta") else (),
            no_hecho=(detalle,),
        )
    hechas["medicion.informe"] = calculo("medicion.informe",
                                         escritura["ruta_destino"], fuente=ctx.firma)

    sin_total = _sin_total(viviendas)
    notas = [
        "El DXF original conserva su sha256 (%s): no se ha tocado."
        % (escritura.get("sello_origen_sha256") or "")[:12],
        "%d vivienda(s) medida(s), separadas por %s."
        % (len(viviendas), medicion.get("agrupacion") or "—"),
    ]
    if sin_total:
        notas.append(
            "%d vivienda(s) sin superficie útil total: %s. Las piezas están medidas; lo "
            "que falta es una decisión del arquitecto, no un cálculo."
            % (len(sin_total), ", ".join(str(v["vivienda"]) for v in sin_total)))

    no_hecho = tuple(
        "«%s» no lleva superficie útil total: %s" % (v["vivienda"], "; ".join(v["impedimentos"]))
        for v in sin_total
    )
    if medicion.get("rotulos_sin_piezas"):
        no_hecho += (
            "el plano rotula %s y ningún recinto ha ido a parar ahí: puede ser una "
            "etiqueta de otra planta o de una leyenda, o una vivienda sin medir"
            % ", ".join("«%s»" % r for r in medicion["rotulos_sin_piezas"]),
        )

    return ResultadoDeSkill(
        afirmaciones=tuple(hechas.values()),
        entregables=(
            Entregable(nombre="Medición de superficies útiles", tipo="pdf",
                       ruta=escritura["ruta_destino"],
                       sello=escritura.get("sello_destino_sha256")),
        ),
        no_hecho=no_hecho,
        notas=tuple(notas),
    )


# --- Las verificaciones -----------------------------------------------------

def _ningun_total_publicado_con_impedimento(resultado) -> Any:
    """La regla dura del módulo de medición, comprobada sobre lo entregado.

    `analyzer/medicion.py` ya la hace cumplir al construir la vivienda. Esto la
    vuelve a mirar sobre lo que ha salido, que es lo que queda en el acta. Dos
    comprobaciones del mismo invariante en capas distintas no es redundancia: es
    lo que hace que quitar una no lo desactive.
    """
    for vivienda in valor(resultado, "medicion.viviendas") or ():
        publicadas = [c for c in ("util_interior_m2", "util_exterior_m2")
                      if vivienda.get(c) is not None]
        if publicadas and vivienda.get("impedimentos"):
            return ("«%s» publica %s y a la vez declara que algo lo impide (%s): una "
                    "cifra que puede estar mal es peor que su ausencia"
                    % (vivienda.get("vivienda"), " y ".join(publicadas),
                       "; ".join(vivienda["impedimentos"])))
    return True


def _todo_total_suma_todas_sus_piezas(resultado) -> Any:
    """Una cifra que se deja una pieza fuera es superficie perdida en silencio.

    Es el modo de fallo más caro de un cuadro de superficies: la cifra parece
    razonable, cuadra consigo misma y le falta una habitación.

    **Aquí sí se suman interior y exterior, y es el único sitio donde se hace.**
    No es reconstruir el `total_util_m2` retirado: es el invariante de que entre
    las dos no se ha perdido ninguna pieza — cuando ambas se publican, no queda
    ninguna `sin_clasificar` (bloquearía), así que interior + exterior tiene que
    dar exactamente la suma de las piezas. Esta suma no sale nunca de esta
    comprobación.
    """
    for vivienda in valor(resultado, "medicion.viviendas") or ():
        interior = vivienda.get("util_interior_m2")
        exterior = vivienda.get("util_exterior_m2")
        if interior is None or exterior is None:
            continue
        total = round(float(interior) + float(exterior), 2)
        piezas = round(sum(float(p.get("area_m2") or 0.0)
                           for p in vivienda.get("piezas") or ()), 2)
        if abs(piezas - float(total)) > 0.005:
            return ("«%s» totaliza %s m² y sus piezas suman %s m²: hay superficie que no "
                    "está en el total" % (vivienda.get("vivienda"), total, piezas))
    return True


def _toda_pieza_dice_donde_esta(resultado) -> Any:
    """Una superficie que no se puede ir a comprobar al plano no es una medición."""
    for vivienda in valor(resultado, "medicion.viviendas") or ():
        for pieza in vivienda.get("piezas") or ():
            if not (pieza.get("capa") or "").strip():
                return ("una pieza de «%s» no dice en qué capa del DXF está, y una "
                        "superficie que no se puede localizar no se puede comprobar"
                        % vivienda.get("vivienda"))
    return True


def _el_original_no_se_ha_tocado(resultado) -> Any:
    """Sin esto, la nota del acta sería una frase y no una comprobación."""
    if not resultado.entregables:
        return True
    for nota in resultado.notas:
        if "conserva su sha256" in nota:
            return True
    return ("se ha entregado una medición y el resultado no acredita que el DXF "
            "original siga intacto")


def _la_medicion_no_califica(resultado) -> Any:
    """La frontera con el criterio profesional (`D-7`), comprobada y no prometida.

    Decir «este solape es grave» o «esta vivienda es pequeña» es criterio de
    arquitecto, y el de ArchMuse está sin firmar. Mientras esta verificación
    pase, esta Skill mide. El vocabulario se lee del que ya fija la revisión de
    coherencia en vez de copiarse: dos listas de la misma frontera acabarían
    diciendo cosas distintas.
    """
    for vivienda in valor(resultado, "medicion.viviendas") or ():
        texto = " ".join(str(m) for m in vivienda.get("impedimentos") or ()).lower()
        for palabra in PALABRAS_DE_GRAVEDAD:
            if palabra in texto:
                return ("«%s» califica lo que ha medido («%s»): esta Skill dice qué hay y "
                        "cuánto mide, y el criterio lo pone el arquitecto"
                        % (vivienda.get("vivienda"), palabra.strip()))
    return True


SKILLS = (
    Skill(
        id="superficies.medicion_de_planta",
        version="1.0.0",
        dominio="superficies",
        objetivo=(
            "Medir la superficie útil de todas las viviendas de una planta, pieza a "
            "pieza y con la procedencia de cada cifra, y entregar el documento. No "
            "necesita que el plano traiga ningún cuadro de superficies dibujado y no se "
            "rinde ante una planta con varias viviendas."
        ),
        cuando_usarla=(
            "Cuando el objetivo sea saber cuánto mide cada vivienda de una planta, o "
            "cuando el plano tenga más de una vivienda, o cuando no traiga ningún cuadro "
            "de superficies dibujado. NO usarla si el plano trae su ACAD_TABLE de cuadro "
            "y lo que se quiere es rellenarlo: para eso está "
            "superficies.cuadro_de_vivienda, que escribe el cuadro en una copia del "
            "propio DXF. Tampoco sirve para comprobar normativa ni superficies mínimas: "
            "esta Skill mide y no dictamina. Para mirar sin generar ningún documento "
            "está la capacidad plano.medicion_de_la_planta, que no escribe ni pide "
            "autorización."
        ),
        procedimiento=(
            "1. Leer el plano comprobando la unidad en la que está dibujado. Si no se "
            "puede saber, PARAR y preguntar: un plano en milímetros leído como metros da "
            "viviendas de sesenta millones de metros cuadrados y no falla por ningún "
            "lado.",
            "2. Separar las viviendas por los rótulos «VT…» que el propio arquitecto "
            "puso en el plano. Si el plano no los trae, agrupar por proximidad y decir "
            "que eso es una suposición de ArchMuse.",
            "3. Auditar ese reparto: una pieza casi equidistante entre dos viviendas se "
            "declara, no se asigna a la más cercana y se calla.",
            "4. Medir cada recinto sobre su propio contorno y clasificarlo como "
            "superficie interior o exterior por su rótulo. Lo que no se reconozca se "
            "enseña con su superficie, sin asignarlo a ninguno de los dos.",
            "5. Cruzar la suma de las piezas contra la superficie que ocupan realmente. "
            "Si no coinciden, hay metros contados dos veces y la diferencia exacta es lo "
            "que lo prueba.",
            "6. Totalizar SOLO las viviendas en las que no haya quedado nada pendiente. "
            "En las demás, escribir el motivo con su magnitud donde iría el total: un "
            "total que puede estar mal se copia a la memoria del proyecto, y la ausencia "
            "de total se pregunta.",
            "7. Entregar el documento con la procedencia de cada cifra —qué recinto, con "
            "qué rótulo, en qué capa—, la geometría que no ha entrado en la medición y "
            "lo que este trabajo no comprueba.",
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta_dxf": {"type": "string",
                             "description": "El DXF del arquitecto. Sólo se lee."},
                "ruta_informe": {"type": "string",
                                 "description": ("Dónde se escribe la medición en PDF. "
                                                 "No puede ser el propio plano.")},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de recintos, si ya está confirmada."},
                "factor_escala": {"type": ["number", "null"],
                                  "description": ("Multiplicador a metros, si ya está "
                                                  "confirmado.")},
            },
            "required": ["ruta_dxf", "ruta_informe"],
            "additionalProperties": False,
        },
        # Nada de la memoria del proyecto: el plano viene en la petición. Es lo
        # que hace que esta Skill sirva también para un DXF ajeno.
        requiere=(),
        capacidades=("plano.medicion_de_la_planta", "plano.entregable_en_pdf"),
        produce=PRODUCE,
        funcion=_ejecutar,
        verificaciones=(
            Verificacion(
                nombre="ningun_total_publicado_con_impedimento",
                descripcion=("Ninguna vivienda lleva total si algo impide afirmarlo."),
                funcion=_ningun_total_publicado_con_impedimento,
            ),
            Verificacion(
                nombre="todo_total_suma_todas_sus_piezas",
                descripcion="Un total publicado incluye todas las piezas de su vivienda.",
                funcion=_todo_total_suma_todas_sus_piezas,
            ),
            Verificacion(
                nombre="toda_pieza_dice_donde_esta",
                descripcion="Toda pieza medida dice en qué capa del DXF se puede ver.",
                funcion=_toda_pieza_dice_donde_esta,
            ),
            Verificacion(
                nombre="el_original_no_se_ha_tocado",
                descripcion="El DXF de entrada conserva su sha256.",
                funcion=_el_original_no_se_ha_tocado,
            ),
            Verificacion(
                nombre="la_medicion_no_califica",
                descripcion=("La medición dice qué hay y cuánto mide; el criterio lo "
                             "pone el arquitecto."),
                funcion=_la_medicion_no_califica,
            ),
        ),
        efectos=(ESCRIBE_FICHERO,),
        limitaciones=(
            "es superficie útil, no construida: no incluye espesores de muro",
            "no comprueba normativa ni ningún mínimo de superficie: mide, no dictamina",
            "no rellena el cuadro de superficies del DXF ni escribe nada en el plano: "
            "para eso está superficies.cuadro_de_vivienda",
            "el reparto entre viviendas sale de los rótulos «VT…» del plano; sin ellos "
            "se agrupa por proximidad y eso es una suposición de ArchMuse",
            "el ámbito interior o exterior de una pieza sale de su rótulo, no de su "
            "geometría: una pieza mal rotulada se clasifica mal",
            "no lee muros, huecos ni carpintería: sólo los recintos de la capa de áreas",
        ),
    ),
)
