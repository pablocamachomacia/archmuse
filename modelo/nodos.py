# -*- coding: utf-8 -*-
"""C2 — Los cinco nodos de E1, y los seis que existen sólo como presencia.

    Proyecto ──► Edificio ──► Planta ──► Unidad ──► Espacio
      (1)         (1, supuesto)  (1, supuesta)  (n)      (n)

**Por qué cinco y no once.** `Parcela`, `Muro`, `Hueco`, `Pilar`,
`Instalación` y `Zona común` están en el catálogo de
`KNOWLEDGE_GRAPH.md` §2 y **no tienen clase aquí**: existen únicamente como
entrada en `Proyecto.presencia`, con su estado declarado. Siete clases vacías
durante meses son una invitación a que alguien las rellene con valores
plausibles para que «funcione» (§8.1). `Muro` queda fuera aunque sea inferible
del hueco entre polígonos: materializarlo cambiaría lo que ven las reglas, y
E1 tiene que ser demostrablemente neutro.

**Lo que ningún nodo lleva, dicho por su nombre.** `iluminacion`,
`ventilacion`, `orientacion`, `cumple`, `passed`, `puntuacion`, `score`,
`problemas`, `superficie_util`, `eficiencia`. Son conclusiones, y una
conclusión tiene evidencia, confianza, procedencia y fecha de caducidad —todo
eso ya tiene sitio en `FACT_MODEL.md`—; como campo de un nodo llegaría
desnuda. La lista está en `LISTA_NEGRA` y la comprueba
`tests/test_modelo_fronteras.py` sobre los campos reales de estas dataclases,
no sobre la buena intención de quien las lea.

**Los nombres de formato viven en `Procedencia` y en ningún otro sitio.** Una
«capa» es un concepto de DXF, no de arquitectura (principio P6). Hoy
`parser.Room.layer` incumpliría esa regla, y es la señal exacta de que `Room`
no es un nodo del modelo sino un residuo del lector.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .atributo import Atributo

# --- Catálogo de tipos de nodo (los once de KNOWLEDGE_GRAPH.md §2) ---------
# Los cinco primeros tienen clase; los seis siguientes, sólo presencia.

TIPO_PROYECTO = "proyecto"
TIPO_EDIFICIO = "edificio"
TIPO_PLANTA = "planta"
TIPO_UNIDAD = "unidad"
TIPO_ESPACIO = "espacio"
TIPO_PARCELA = "parcela"
TIPO_MURO = "muro"
TIPO_HUECO = "hueco"
TIPO_PILAR = "pilar"
TIPO_INSTALACION = "instalacion"
TIPO_ZONA_COMUN = "zona_comun"

CATALOGO = (
    TIPO_PROYECTO, TIPO_EDIFICIO, TIPO_PLANTA, TIPO_UNIDAD, TIPO_ESPACIO,
    TIPO_PARCELA, TIPO_MURO, TIPO_HUECO, TIPO_PILAR, TIPO_INSTALACION,
    TIPO_ZONA_COMUN,
)

MATERIALIZADOS = (TIPO_PROYECTO, TIPO_EDIFICIO, TIPO_PLANTA, TIPO_UNIDAD, TIPO_ESPACIO)

# --- Estados de presencia (`KNOWLEDGE_GRAPH.md` §0.4) ----------------------
# La diferencia entre «no hay» y «no lo veo». Sin esto, la ausencia de nodos de
# un tipo no es interpretable, y una inferencia negativa sobre datos que nunca
# existieron falla en silencio y en la dirección tranquilizadora.

PRESENCIA_OBSERVADO = "observado"
PRESENCIA_INFERIDO = "inferido"
PRESENCIA_NO_OBSERVABLE = "no_observable"
PRESENCIA_AUSENCIA_VERIFICADA = "ausencia_verificada"

PRESENCIAS = (PRESENCIA_OBSERVADO, PRESENCIA_INFERIDO,
              PRESENCIA_NO_OBSERVABLE, PRESENCIA_AUSENCIA_VERIFICADA)

# --- Lista negra de campos evaluativos (§0.1) ------------------------------

LISTA_NEGRA = (
    "iluminacion", "ventilacion", "orientacion", "cumple", "passed",
    "puntuacion", "score", "problemas", "superficie_util", "eficiencia",
    "rating", "valoracion", "severidad", "issues", "hallazgos",
)

# Campos cuyo nombre viene de un formato de fichero. Sólo `Procedencia` puede
# tenerlos (principio P6, contrato C7.6).
NOMBRES_DE_FORMATO = ("capa", "layer", "block", "bloque", "handle", "guid")


@dataclass(frozen=True)
class Procedencia:
    """De dónde salió un nodo, en un esquema canónico e independiente del
    formato de origen.

    Es el **único** sitio del modelo donde puede aparecer un nombre de
    formato. Que `capa` viva aquí y no en `Espacio` es lo que permite que un
    día un `Espacio` venga de IFC sin que ninguna regla se entere.
    """

    formato: str = ""            # "dxf" | "ifc" | "generado" | "declarado"
    fichero: str = ""
    capa: Optional[str] = None   # nombre de formato: aquí, y en ningún otro sitio
    id_nativo: Optional[str] = None

    def a_dict(self) -> dict:
        return {"formato": self.formato, "fichero": self.fichero,
                "capa": self.capa, "id_nativo": self.id_nativo}


@dataclass(frozen=True)
class Espacio:
    """El nodo central, y hoy el único con datos observados de verdad."""

    id: str
    concepto: str
    unidad_id: str
    planta_id: str
    rotulo: Optional[str]          # el texto literal del plano, SIN interpretar
    tipo: Atributo                 # tipo canónico + origen (nunca un `str` desnudo)
    geometrias: Dict[str, str] = field(default_factory=dict)
    procedencia: Procedencia = field(default_factory=Procedencia)
    # Tipos que también casaban con el rótulo. No se resuelve la ambigüedad en
    # silencio: se registra. "SALÓN-COCINA" es un caso real.
    tipos_ambiguos: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Unidad:
    """Vivienda o local: agrupación de espacios con identidad propia."""

    id: str
    concepto: str
    planta_id: str
    etiqueta: Atributo             # observada si el plano la rotula; derivada si se agrupó
    uso: Atributo
    espacios: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Planta:
    """El ámbito que el DB-SI indexa casi siempre.

    En E1 hay exactamente una, con `numero` y `cota_base_m` UNKNOWN: un DXF de
    distribución no dice qué planta es. CAP-4 ya resolvió eso preguntando en
    vez de adivinar, y aquí se hereda ese criterio — la planta declarada del
    formulario no entra en el modelo todavía porque `/api/analizar` la resuelve
    aguas arriba y E1 no cambia ese flujo.
    """

    id: str
    concepto: str
    edificio_id: str
    numero: Atributo
    cota_base_m: Atributo
    altura_libre_m: Atributo
    unidades: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Edificio:
    id: str
    concepto: str
    plantas: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Proyecto:
    """Raíz del grafo. Lleva lo que se sabe y, sobre todo, lo que no se sabe.

    `presencia` cubre los ONCE tipos del catálogo, no los cinco
    materializados: es la diferencia entre «esta vivienda no tiene ventanas» y
    «este plano no dibuja ventanas», y sin ella ninguna de las dos frases se
    puede distinguir de la otra (invariante I6).
    """

    id: str
    concepto: str
    escala: Atributo
    norte_grados: Atributo
    tipologia: Atributo
    ciudad: Atributo
    procedencia: Procedencia = field(default_factory=Procedencia)
    presencia: Dict[str, str] = field(default_factory=dict)
    edificios: Tuple[str, ...] = ()
