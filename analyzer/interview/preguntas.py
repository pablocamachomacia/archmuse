"""Catálogo declarativo de preguntas — Fase C, tarea C1.

**Datos, no lógica imperativa por pregunta** (criterio de aceptación de C1):
cada `Pregunta` es un registro inmutable; el motor (`motor.py`) es el único
sitio con lógica de decisión. Este módulo no importa `motor.py` ni
`claude_interprete.py` — nada aquí llama a Claude ni sabe cómo se presenta
una pregunta en pantalla.

Las 15 preguntas son las de la Parte I del PRD v2
(`docs/prd/2026-08-12-entrevistador-generador.md` §6) — **no se inventa una
segunda taxonomía**: el texto literal de cada pregunta es el del PRD, y el
comentario de cada entrada cita el número de esa lista. Se añaden, aparte de
esas 15, las sub-preguntas de la bifurcación de la pregunta 3 (C4 del plan:
"la rama no tomada nunca se pregunta") y una pregunta de respaldo para
`programa.tipologia`, que ninguna de las 15 cubre directamente — ver la nota
al final del módulo.

`especificacion_id` usa notación `categoría.campo`, igual que los ejemplos
del PRD v2 §22.2 (`"solar.superficie_m2"`, `"prioridades.trade_off"`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .modelo import CATEGORIAS_ESPECIFICACION, _validar_enum

# --- Catálogos cerrados propios de este módulo -----------------------------

#: Formato de una pregunta — igual que el PRD v2 §6: Abierta / Opción /
#: Condicional (aquí en minúsculas, valor de dato, no de presentación).
TIPOS_PREGUNTA = ("abierta", "opcion", "condicional")

#: Cuándo requiere Claude, con un tercer estado deliberado además de sí/no:
#: `"condicional"` es el caso de las preguntas 9 y 11 (PRD v2 §21.2: "0 si el
#: usuario responde con cifras/opciones simples") — el motor intenta primero
#: un parseo determinista y solo recurre a Claude si ese parseo falla.
NIVELES_IA = ("nunca", "siempre", "condicional")

#: Agrupación de turnos (PRD v2 §21.3). "fijo" = preguntas 1, 4 y 5,
#: presentadas juntas en un único turno e interpretadas en una sola llamada.
#: "adaptativo" = todo lo demás, una pregunta por turno, elegida por la cola
#: priorizada del motor (§25).
BLOQUES = ("fijo", "adaptativo")


@dataclass(frozen=True)
class CondicionActivacion:
    """Condición declarativa de activación — nunca una función arbitraria,
    para que el catálogo siga siendo datos y el motor sea el único que
    interpreta condiciones (mismo principio que la propia `Pregunta`)."""

    especificacion_id: str
    operador: str  # "presente" | "ausente" | "igual" | "distinto" | "en" | "no_en"
    valor: Any = None

    def __post_init__(self) -> None:
        _validar_enum(
            self.operador,
            ("presente", "ausente", "igual", "distinto", "en", "no_en"),
            "operador",
            "CondicionActivacion",
        )


@dataclass(frozen=True)
class Pregunta:
    """Una entrada del catálogo. Todos los atributos pedidos explícitamente:
    id estable, categoría, tipo, condición de activación, qué pretende
    obtener, si es bloqueante, qué campos alimenta, si requiere IA."""

    pregunta_id: str
    numero_prd: Optional[int]  # número en la lista de §6 del PRD v2; None si es sub-pregunta o respaldo
    categoria: str
    tipo: str
    texto: str
    que_pretende_obtener: str
    especificacion_ids: tuple[str, ...]
    bloque: str
    requiere_ia: str = "nunca"
    opciones: Optional[tuple[str, ...]] = None
    condicion_activacion: Optional[CondicionActivacion] = None
    #: Asesoramiento breve por opción (2026-08-15, "Materiales y Calidades" -- a petición explícita: "textos
    #: breves de ayuda... debajo de cada opción técnica"). `None` para cualquier pregunta que no lo necesite
    #: (la inmensa mayoría) -- cuando existe, debe cubrir TODAS las `opciones`, nunca solo alguna (para no
    #: dejar un hueco silencioso en la interfaz).
    asesoramiento: Optional[dict[str, str]] = None

    def __post_init__(self) -> None:
        _validar_enum(self.categoria, CATEGORIAS_ESPECIFICACION, "categoria", "Pregunta")
        _validar_enum(self.tipo, TIPOS_PREGUNTA, "tipo", "Pregunta")
        _validar_enum(self.requiere_ia, NIVELES_IA, "requiere_ia", "Pregunta")
        _validar_enum(self.bloque, BLOQUES, "bloque", "Pregunta")
        if not self.especificacion_ids:
            raise ValueError("Pregunta.especificacion_ids no puede estar vacío: %r" % (self.pregunta_id,))
        if self.asesoramiento is not None:
            faltan = set(self.opciones or ()) - set(self.asesoramiento)
            if faltan:
                raise ValueError(
                    "Pregunta.asesoramiento de %r no cubre todas las opciones (faltan: %s)" % (self.pregunta_id, faltan)
                )

    def es_bloqueante(self, imprescindibles: tuple[str, ...]) -> bool:
        """Bloqueante = alimenta directamente al menos un dato imprescindible
        (PRD v2 §2). Se calcula, no se declara a mano, para que nunca quede
        desincronizado del catálogo de imprescindibles."""
        return bool(set(self.especificacion_ids) & set(imprescindibles))


# --- Los 8 datos imprescindibles (PRD v2 §2) --------------------------------

IMPRESCINDIBLES: tuple[str, ...] = (
    "contexto.ciudad",  # 1. Ciudad/municipio
    "programa.tipologia",  # 2. Uso del edificio y tipología
    "solar.superficie_m2",  # 3. Superficie del solar
    "solar.forma",  # 4. Forma/dimensiones del solar
    "programa.num_viviendas_mix",  # 5. Nº de viviendas deseado y mix aproximado
    "prioridades.trade_off",  # 6. Prioridad principal ante conflicto
    "usuarios.accesibilidad",  # 7. Accesibilidad requerida
    "orientacion.real_parcela",  # 8. Orientación real de la parcela
)

#: Campos que la interpretación del bloque fijo (Claude, llamada 1) puede
#: producir de forma oportunista además de los que las preguntas 1/4/5
#: piden directamente — el usuario a menudo menciona ciudad, tipología o
#: número de viviendas al describir el proyecto con sus palabras (pregunta
#: 1). No son "especificacion_ids" de ninguna pregunta del catálogo porque
#: ninguna pregunta los pide *directamente*; el motor los reconoce igual
#: porque comprueba `respuestas_interpretadas`, no el catálogo (ver motor.py
#: `campo_resuelto`).
CAMPOS_OPORTUNISTAS_BLOQUE_FIJO: tuple[str, ...] = (
    "contexto.ciudad",
    "programa.tipologia",
    "programa.num_viviendas_mix",
    "prioridades.trade_off",
    "identidad.referencias_esteticas",
)


# --- El catálogo -----------------------------------------------------------

_P3 = CondicionActivacion(especificacion_id="parcela.estado_tenencia", operador="presente")

PREGUNTAS: tuple[Pregunta, ...] = (
    # --- Bloque fijo: 1, 4, 5 (PRD v2 §21.3, se presentan juntas) ---------
    Pregunta(
        pregunta_id="p1",
        numero_prd=1,
        categoria="programa_necesidades",
        tipo="abierta",
        texto=(
            "Describe con tus palabras el proyecto que tienes en la cabeza — y si quieres, "
            "en una frase, cómo te gustaría que se sintiera por dentro."
        ),
        que_pretende_obtener="Programa preliminar en lenguaje natural, y la sensación buscada (fusiona la antigua pregunta 15 de v1).",
        especificacion_ids=("programa.descripcion_libre", "programa.sensacion_buscada"),
        bloque="fijo",
        requiere_ia="siempre",
    ),
    Pregunta(
        pregunta_id="p4",
        numero_prd=4,
        categoria="prioridades_trade_offs",
        tipo="abierta",
        texto="¿Qué es lo que NO puede faltar en este proyecto, pase lo que pase?",
        que_pretende_obtener="No-negociables declarados explícitamente por el usuario.",
        especificacion_ids=("prioridades.no_negociables",),
        bloque="fijo",
        requiere_ia="siempre",
    ),
    Pregunta(
        pregunta_id="p5",
        numero_prd=5,
        categoria="prioridades_trade_offs",
        tipo="abierta",
        texto="¿Y qué es lo que menos te importa, aunque otros lo consideren importante?",
        que_pretende_obtener="Qué puede sacrificarse — la otra mitad del trade-off de prioridades.",
        especificacion_ids=("prioridades.lo_de_menos_importa",),
        bloque="fijo",
        requiere_ia="siempre",
    ),
    # --- Bloque adaptativo: el resto, una por turno -----------------------
    Pregunta(
        pregunta_id="p2",
        numero_prd=2,
        categoria="usuarios_forma_vida",
        tipo="opcion",
        texto="¿Este proyecto es para vivir tú, para vender, para alquilar, o todavía no lo sabes?",
        que_pretende_obtener="Para quién es el edificio — condiciona prioridades de diseño.",
        especificacion_ids=("usuarios.destino",),
        bloque="adaptativo",
        opciones=("vivir", "vender", "alquilar", "no_lo_sabe"),
    ),
    Pregunta(
        pregunta_id="p3",
        numero_prd=3,
        categoria="parcela",
        tipo="condicional",
        texto="¿Ya tienes la parcela, o todavía la estás buscando/imaginando?",
        que_pretende_obtener="Gateway de la categoría Parcela — determina si lo que sigue es un hecho o una intención.",
        especificacion_ids=("parcela.estado_tenencia",),
        bloque="adaptativo",
        opciones=("tengo_parcela", "buscando_parcela"),
    ),
    Pregunta(
        pregunta_id="p3_ciudad",
        numero_prd=None,
        categoria="contexto_ubicacion",
        tipo="abierta",
        texto="¿En qué ciudad o municipio está (o buscas/imaginas) el solar?",
        que_pretende_obtener="Ciudad/municipio (imprescindible 1) — sub-pregunta de la 3, PRD v2 §1 categoría 1.",
        especificacion_ids=("contexto.ciudad",),
        bloque="adaptativo",
        condicion_activacion=_P3,
    ),
    Pregunta(
        pregunta_id="p3_superficie",
        numero_prd=None,
        categoria="parcela",
        tipo="abierta",
        texto="¿Qué superficie tiene (o buscas), aproximadamente, en metros cuadrados?",
        que_pretende_obtener="Superficie del solar (imprescindible 3) — sub-pregunta de la 3.",
        especificacion_ids=("solar.superficie_m2",),
        bloque="adaptativo",
        condicion_activacion=_P3,
    ),
    Pregunta(
        pregunta_id="p3_forma",
        numero_prd=None,
        categoria="parcela",
        tipo="abierta",
        texto=(
            "¿Cómo es la forma del solar — rectangular, en esquina, irregular...? Si no lo sabes o "
            "prefieres que lo decidamos nosotros, dilo y lo tomamos como \"irregular, decídelo tú\"."
        ),
        que_pretende_obtener="Forma/dimensiones del solar (imprescindible 4) — admite explícitamente \"decídelo tú\" (PRD v2 §2.4).",
        especificacion_ids=("solar.forma",),
        bloque="adaptativo",
        condicion_activacion=_P3,
    ),
    Pregunta(
        pregunta_id="p6",
        numero_prd=6,
        categoria="programa_necesidades",
        tipo="opcion",
        texto="Si tuvieras que elegir: ¿viviendas más grandes y menos, o más pequeñas y más?",
        que_pretende_obtener="Dirección del mix de viviendas (imprescindible 5) — preferencia cualitativa, nunca un número (§18 del PRD, Fase D interpola).",
        especificacion_ids=("programa.num_viviendas_mix",),
        bloque="adaptativo",
        opciones=("mas_grandes_menos_viviendas", "mas_pequenas_mas_viviendas"),
    ),
    Pregunta(
        pregunta_id="p7",
        numero_prd=7,
        categoria="restricciones_normativas",
        tipo="abierta",
        texto="¿Sabes cuántas plantas puedes construir en tu solar, o necesitas que te ayudemos a estimarlo?",
        que_pretende_obtener=(
            "Plantas máximas — honesto sobre el límite (PRD v2 §6.4): si no se sabe, Hipótesis con "
            "motivo \"sin verificación normativa municipal disponible\", nunca una comprobación inventada."
        ),
        especificacion_ids=("restricciones.plantas_maximas",),
        bloque="adaptativo",
    ),
    Pregunta(
        pregunta_id="p8",
        numero_prd=8,
        categoria="orientacion_clima",
        tipo="condicional",
        texto=(
            "¿Hacia dónde da la fachada principal de tu parcela — norte, sur, este, oeste, o una "
            "combinación? Si tienes la dirección, dínosla y te ayudamos con un mapa."
        ),
        que_pretende_obtener=(
            "Orientación REAL de la parcela (imprescindible 8, hecho geométrico) — nunca una preferencia "
            "solar interior, que es una pregunta distinta y opcional (PRD v2 §6.3)."
        ),
        especificacion_ids=("orientacion.real_parcela",),
        bloque="adaptativo",
        opciones=("norte", "sur", "este", "oeste", "noreste", "noroeste", "sureste", "suroeste", "combinacion"),
    ),
    Pregunta(
        pregunta_id="p9",
        numero_prd=9,
        categoria="presupuesto",
        tipo="abierta",
        texto="¿Cuánto te gustaría gastar aproximadamente? Puede ser una horquilla.",
        que_pretende_obtener="Presupuesto — opcional (PRD v2 §3), decisión A del contrato: se guarda, el generador actual no lo usa todavía.",
        especificacion_ids=("presupuesto.cifra_horquilla",),
        bloque="adaptativo",
        requiere_ia="condicional",
    ),
    Pregunta(
        pregunta_id="p10",
        numero_prd=10,
        categoria="sostenibilidad_eficiencia",
        tipo="opcion",
        texto=(
            "¿Qué pesa más para ti: ahorrar en la factura energética a largo plazo, o mantener bajo "
            "el coste de construcción ahora?"
        ),
        que_pretende_obtener="Prioridad de sostenibilidad — opcional, decisión A del contrato.",
        especificacion_ids=("sostenibilidad.prioridad",),
        bloque="adaptativo",
        opciones=("ahorro_energetico_largo_plazo", "coste_construccion_bajo"),
    ),
    Pregunta(
        pregunta_id="p11",
        numero_prd=11,
        categoria="identidad_arquitectonica",
        tipo="abierta",
        texto="Cuéntanos 2 o 3 casas o edificios que te gusten — fotos, nombres, o una descripción.",
        que_pretende_obtener="Referencias estéticas / carácter — decisión B del contrato (blanda, entra en contexto_cualitativo en Fase D).",
        especificacion_ids=("identidad.referencias_esteticas",),
        bloque="adaptativo",
        requiere_ia="condicional",
    ),
    Pregunta(
        pregunta_id="p12",
        numero_prd=12,
        categoria="entorno_privacidad",
        tipo="opcion",
        texto="¿Cuánta privacidad necesitas frente a la calle o los vecinos: mucha, la normal, o te da igual?",
        que_pretende_obtener="Privacidad — decisión B del contrato (blanda).",
        especificacion_ids=("privacidad.necesidad",),
        bloque="adaptativo",
        opciones=("mucha", "normal", "le_da_igual"),
    ),
    Pregunta(
        pregunta_id="p13",
        numero_prd=13,
        categoria="usuarios_forma_vida",
        tipo="opcion",
        texto="¿Va a vivir, o podría vivir en el futuro, alguien con movilidad reducida?",
        que_pretende_obtener="Accesibilidad requerida (imprescindible 7) — decisión B del contrato (dura).",
        especificacion_ids=("usuarios.accesibilidad",),
        bloque="adaptativo",
        opciones=("si", "no", "no_lo_sabe"),
    ),
    Pregunta(
        pregunta_id="p14",
        numero_prd=14,
        categoria="espacios_exteriores",
        tipo="opcion",
        texto=(
            "¿Prefieres que cada vivienda tenga su propio espacio exterior aunque sea a costa de "
            "metros interiores, o prefieres aprovechar cada metro cuadrado por dentro?"
        ),
        que_pretende_obtener="Preferencia de espacios exteriores — opcional.",
        especificacion_ids=("exteriores.preferencia",),
        bloque="adaptativo",
        opciones=("espacio_exterior_propio", "aprovechar_metros_interiores"),
    ),
    Pregunta(
        pregunta_id="p15",
        numero_prd=15,
        categoria="relaciones_espaciales_circulacion",
        tipo="opcion",
        texto="¿Te gusta la cocina integrada con el salón (abierta), o prefieres que quede separada (cerrada)?",
        que_pretende_obtener=(
            "Cocina abierta/cerrada (PRD v2 §5.1) — la única relación espacial que se pregunta; "
            "el resto son reglas fijas del Motor, no del usuario."
        ),
        especificacion_ids=("relaciones_espaciales.cocina",),
        bloque="adaptativo",
        opciones=("abierta", "cerrada"),
    ),
    # --- Preguntas de respaldo: imprescindibles sin pregunta directa entre
    # las 15 (ver nota al final del módulo) -------------------------------
    Pregunta(
        pregunta_id="p_trade_off_directo",
        numero_prd=None,
        categoria="prioridades_trade_offs",
        tipo="opcion",
        texto=(
            "Si tuvieras que priorizar solo una cosa en caso de conflicto — más superficie, más luz, "
            "menor coste, o más número de viviendas — ¿cuál eligirías?"
        ),
        que_pretende_obtener=(
            "Prioridad principal ante conflicto (imprescindible 6) cuando las preguntas 1/4/5 no lo dejaron "
            "claro — respaldo determinista, la interpretación del bloque fijo es siempre la vía preferente."
        ),
        especificacion_ids=("prioridades.trade_off",),
        bloque="adaptativo",
        opciones=("superficie", "luz", "coste", "numero_viviendas"),
    ),
    Pregunta(
        pregunta_id="p_tipologia_directa",
        numero_prd=None,
        categoria="programa_necesidades",
        tipo="opcion",
        texto="¿Qué tipo de edificio es: una vivienda unifamiliar, un edificio plurifamiliar de varias viviendas, u otra cosa?",
        que_pretende_obtener=(
            "Uso/tipología (imprescindible 2) cuando no se ha podido inferir de la pregunta 1 — respaldo "
            "determinista, nunca la primera pregunta que se hace (principio 6: evitar preguntar lo derivable)."
        ),
        especificacion_ids=("programa.tipologia",),
        bloque="adaptativo",
        opciones=("unifamiliar", "plurifamiliar", "otra"),
    ),
    # --- Materiales, fachadas, calidades e interiorismo (2026-08-15, a petición explícita) ----------------
    # Cuatro preguntas nuevas, ninguna imprescindible (no están en `IMPRESCINDIBLES`) -- mismo estatus que
    # p9-p15: enriquecen el pliego pero nunca bloquean el cierre de la entrevista si quedan sin responder.
    # `tipo="condicional"` (no "opcion") a propósito: es el mismo mecanismo que ya usan p3/p8 para admitir
    # tanto los botones/chips cerrados como texto libre fuera de catálogo (`motor._procesar_determinista`) --
    # exactamente lo que pide el encargo ("selección rápida... como respuesta en texto libre"), sin tocar
    # ni una línea del motor. `asesoramiento` es el texto de ayuda que se muestra bajo cada chip.
    Pregunta(
        pregunta_id="p_fachada",
        numero_prd=None,
        categoria="identidad_arquitectonica",
        tipo="condicional",
        texto="¿Qué tipo de fachada te imaginas para el edificio?",
        que_pretende_obtener="Material/sistema de fachada preferido -- condiciona la memoria de calidades y las texturas del modelo 3D.",
        especificacion_ids=("materiales.tipo_fachada",),
        bloque="adaptativo",
        opciones=(
            "sate_aislamiento_continuo", "fachada_ventilada_piedra_ceramica", "hormigon_visto",
            "ladrillo_visto_clasico_moderno", "madera_exterior_composite",
        ),
        asesoramiento={
            "sate_aislamiento_continuo": "Excelente aislamiento térmico y bajo mantenimiento; sin apenas puentes térmicos.",
            "fachada_ventilada_piedra_ceramica": "Muy duradera y de aspecto premium; cámara ventilada que mejora el confort térmico.",
            "hormigon_visto": "Estética industrial/contemporánea; requiere una ejecución muy cuidada del encofrado.",
            "ladrillo_visto_clasico_moderno": "Aspecto cálido y atemporal, prácticamente sin mantenimiento.",
            "madera_exterior_composite": "Cálida y natural; el composite reduce el mantenimiento frente a la madera maciza.",
        },
    ),
    Pregunta(
        pregunta_id="p_paleta_colores",
        numero_prd=None,
        categoria="identidad_arquitectonica",
        tipo="condicional",
        texto="¿Qué gama de colores prefieres, por dentro y por fuera?",
        que_pretende_obtener="Paleta de colores preferida -- condiciona el carácter y las texturas sugeridas del modelo 3D.",
        especificacion_ids=("materiales.paleta_colores",),
        bloque="adaptativo",
        opciones=(
            "tonos_neutros_blanco_arena", "tonos_oscuros_gris_antracita_negro",
            "acabados_calidos_madera_piedra", "colores_vivos_contrastes",
        ),
        asesoramiento={
            "tonos_neutros_blanco_arena": "Luminoso y atemporal; amplía visualmente los espacios y envejece bien.",
            "tonos_oscuros_gris_antracita_negro": "Estética sobria y contemporánea; marca mucho el volumen del edificio.",
            "acabados_calidos_madera_piedra": "Sensación acogedora y natural; combina bien con cualquier estilo.",
            "colores_vivos_contrastes": "Carácter e identidad propia; conviene usarlo con medida para no saturar.",
        },
    ),
    Pregunta(
        pregunta_id="p_pavimento",
        numero_prd=None,
        categoria="estructura_sistema_constructivo",
        tipo="condicional",
        texto="¿Qué tipo de suelo o pavimento te gustaría en el interior?",
        que_pretende_obtener="Pavimento interior preferido -- calidades/acabados del pliego.",
        especificacion_ids=("materiales.pavimento",),
        bloque="adaptativo",
        opciones=(
            "parquet_madera_natural", "gres_porcelanico_gran_formato", "microcemento",
            "suelo_radiante_acabado_ceramico",
        ),
        asesoramiento={
            "parquet_madera_natural": "Cálido al tacto y de gran calidad percibida; necesita algo más de mantenimiento.",
            "gres_porcelanico_gran_formato": "Muy resistente y fácil de mantener; juntas mínimas para un look continuo.",
            "microcemento": "Superficie continua sin juntas, muy actual; requiere una base bien preparada.",
            "suelo_radiante_acabado_ceramico": "Confort térmico homogéneo; la cerámica es el acabado que mejor transmite el calor.",
        },
    ),
    Pregunta(
        pregunta_id="p_nivel_calidades",
        numero_prd=None,
        categoria="estructura_sistema_constructivo",
        tipo="condicional",
        texto="¿Qué nivel de calidades y presupuesto de acabados te gustaría?",
        que_pretende_obtener="Nivel de calidades global -- condiciona presupuesto y especificación de acabados de todo el pliego.",
        especificacion_ids=("materiales.nivel_calidades",),
        bloque="adaptativo",
        opciones=("estandar_funcional", "alta_calidad_premium", "lujo_a_medida"),
        asesoramiento={
            "estandar_funcional": "Buena relación calidad-precio, acabados de catálogo, sin renuncias funcionales.",
            "alta_calidad_premium": "Materiales y marcas de gama alta; mejor aislamiento acústico/térmico y acabados más cuidados.",
            "lujo_a_medida": "Diseño y fabricación a medida, materiales singulares; presupuesto y plazos más elevados.",
        },
    ),
)

PREGUNTAS_POR_ID: dict[str, Pregunta] = {p.pregunta_id: p for p in PREGUNTAS}

PREGUNTAS_BLOQUE_FIJO: tuple[Pregunta, ...] = tuple(p for p in PREGUNTAS if p.bloque == "fijo")

#: Nota de diseño (Fase C, no en el PRD literal): las 8 imprescindibles no
#: tienen todas una pregunta directa en la lista de 15 — "ciudad/municipio",
#: "superficie/forma del solar" viven en la bifurcación de la pregunta 3
#: (PRD v2 categoría 2 "Parcela"); "tipología" y "prioridad ante conflicto"
#: no tienen ninguna pregunta literal en el PRD (se esperaba que salieran de
#: la interpretación IA del bloque fijo, pero esa vía es best-effort, no
#: garantizada — un test de esta fase con un usuario que responde "no sé" a
#: todo lo detectó). `p_tipologia_directa` y `p_trade_off_directo` son los
#: respaldos deterministas para esos dos casos — ver el informe de cierre de
#: esta fase para que Pablo pueda auditar esta decisión explícitamente.
